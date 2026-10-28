metadata name = 'Dedicated team network and supported Registry private access'
metadata description = 'No subscription-wide identity role or managed resource group changes.'

@description('Region shared by the workspace and team network.')
param location string

@description('Resource prefix matching the team foundation.')
param prefix string

@description('Team number used to assign a distinct private address space.')
param teamNumber int

@description('Dedicated team Storage resource ID.')
param storageId string

@description('Dedicated team Key Vault resource ID.')
param vaultId string

@description('Team Workspace resource ID required for private compute connectivity.')
param workspaceId string

@description('Shared Registry backing Blob Storage resource ID.')
param registryStorageId string

var tags = {
  project: 'azure-llm-mlops'
  purpose: 'training-demo'
  dataClassification: 'synthetic'
  team: 'team-${teamNumber}'
  costCenter: 'kt-mlops-team-${teamNumber}'
}

resource outboundIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: 'pip-${prefix}-outbound'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static' }
}

resource nat 'Microsoft.Network/natGateways@2024-05-01' = {
  name: 'nat-${prefix}'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: {
    idleTimeoutInMinutes: 4
    publicIpAddresses: [{ id: outboundIp.id }]
  }
}

resource computeNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-${prefix}-compute'
  location: location
  tags: tags
  properties: { securityRules: [] }
}

resource network 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'vnet-${prefix}'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.${teamNumber}.0.0/16'] }
    subnets: [
      {
        name: 'compute'
        properties: {
          addressPrefix: '10.${teamNumber}.0.0/24'
          defaultOutboundAccess: false
          natGateway: { id: nat.id }
          networkSecurityGroup: { id: computeNsg.id }
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: '10.${teamNumber}.1.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
          defaultOutboundAccess: false
        }
      }
    ]
  }
}

var dnsNames = [
  'privatelink.blob.core.windows.net'
  'privatelink.file.core.windows.net'
  'privatelink.vaultcore.azure.net'
  'privatelink.api.azureml.ms'
  'privatelink.notebooks.azure.net'
]

resource zones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for name in dnsNames: {
  name: name
  location: 'global'
  tags: tags
}]

resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (name, index) in dnsNames: {
  parent: zones[index]
  name: prefix
  location: 'global'
  tags: tags
  properties: {
    virtualNetwork: { id: network.id }
    registrationEnabled: false
    resolutionPolicy: name == 'privatelink.blob.core.windows.net' ? 'NxDomainRedirect' : 'Default'
  }
}]

var destinations = [
  { name: 'team-blob', resourceId: storageId, groupId: 'blob', dnsIndices: [0] }
  { name: 'team-file', resourceId: storageId, groupId: 'file', dnsIndices: [1] }
  { name: 'team-vault', resourceId: vaultId, groupId: 'vault', dnsIndices: [2] }
  { name: 'shared-registry-blob', resourceId: registryStorageId, groupId: 'blob', dnsIndices: [0] }
  { name: 'team-workspace', resourceId: workspaceId, groupId: 'amlworkspace', dnsIndices: [3, 4] }
]

resource endpoints 'Microsoft.Network/privateEndpoints@2024-05-01' = [for destination in destinations: {
  name: 'pe-${prefix}-${destination.name}'
  location: location
  tags: tags
  properties: {
    subnet: { id: '${network.id}/subnets/private-endpoints' }
    privateLinkServiceConnections: [
      {
        name: destination.name
        properties: {
          privateLinkServiceId: destination.resourceId
          groupIds: [destination.groupId]
        }
      }
    ]
  }
}]

resource zoneGroups 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = [for (destination, index) in destinations: {
  parent: endpoints[index]
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [for dnsIndex in destination.dnsIndices: {
      name: dnsNames[dnsIndex]
      properties: { privateDnsZoneId: zones[dnsIndex].id }
    }]
  }
}]

@description('Subnet used by private CPU compute nodes, with explicit NAT outbound.')
output computeSubnetId string = '${network.id}/subnets/compute'
