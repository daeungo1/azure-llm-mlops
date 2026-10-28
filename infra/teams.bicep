metadata name = 'KT three-team MLOps cost and identity boundaries'
metadata description = 'Dedicated team resource groups, dependencies and workspaces; existing verified demo retained.'

targetScope = 'subscription'

@description('Azure region for the team resource groups and resources.')
param location string = 'koreacentral'

@description('Entra object ID of the operator uploading synthetic demo assets.')
param operatorPrincipalId string

@description('Operator public egress IPv4 address with /32 prefix.')
param operatorAddressPrefix string

@description('Resource group naming prefix for the three teams.')
param resourceGroupPrefix string = 'rg-kt-mlops-team'

@description('Backing Storage resource ID discovered from the shared AML Registry.')
param registryStorageId string

var teams = range(1, 3)

resource groups 'Microsoft.Resources/resourceGroups@2025-04-01' = [for number in teams: {
  name: '${resourceGroupPrefix}-${number}'
  location: location
  tags: {
    project: 'azure-llm-mlops'
    purpose: 'training-demo'
    dataClassification: 'synthetic'
    team: 'team-${number}'
    costCenter: 'kt-mlops-team-${number}'
  }
}]

module networks 'team-network.bicep' = [for (number, index) in teams: {
  name: 'kt-team-${number}-network'
  scope: groups[index]
  params: {
    location: location
    prefix: 'ktmlops${number}'
    teamNumber: number
    storageId: foundations[index].outputs.storageId
    vaultId: foundations[index].outputs.vaultId
    workspaceId: foundations[index].outputs.workspaceId
    registryStorageId: registryStorageId
  }
}]

module foundations 'main.bicep' = [for (number, index) in teams: {
  name: 'kt-team-${number}-foundation'
  scope: groups[index]
  params: {
    location: location
    prefix: 'ktmlops${number}'
    workspaceName: 'mlw-ktmlops-secure-${number}'
    operatorPrincipalId: operatorPrincipalId
    operatorAddressPrefix: operatorAddressPrefix
    team: 'team-${number}'
    costCenter: 'kt-mlops-team-${number}'
    managedNetworkMode: 'Disabled'
  }
}]

@description('Credential-free SDK configurations for the three team workspaces.')
output configs array = [for (number, index) in teams: foundations[index].outputs.config]

@description('Dedicated Storage IDs defining team data access boundaries.')
output storageIds array = [for (number, index) in teams: foundations[index].outputs.storageId]

@description('Private CPU compute subnet for each team.')
output subnetIds array = [for (number, index) in teams: networks[index].outputs.computeSubnetId]
