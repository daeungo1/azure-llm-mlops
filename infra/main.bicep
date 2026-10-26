metadata name = 'Azure ML CPU MLOps demo'
metadata description = 'Public, authenticated teaching environment. No customer data or GPU resources.'

@description('Azure region for all demo resources.')
param location string = resourceGroup().location

@description('Short resource naming prefix.')
@maxLength(9)
param prefix string = 'ktmlops'

@description('Entra object ID of the user uploading demo assets.')
param operatorPrincipalId string

var suffix = uniqueString(resourceGroup().id)
var tags = {
  project: 'azure-llm-mlops'
  purpose: 'training-demo'
  dataClassification: 'synthetic'
}

resource storage 'Microsoft.Storage/storageAccounts@2025-06-01' = {
  name: 'st${prefix}${suffix}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}

resource vault 'Microsoft.KeyVault/vaults@2025-05-01' = {
  name: 'kv-${take(prefix, 7)}-${take(suffix, 10)}'
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: 'cr${prefix}${suffix}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    anonymousPullEnabled: false
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: 'log-${prefix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: 1 }
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${prefix}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
    IngestionMode: 'LogAnalytics'
  }
}

resource workspace 'Microsoft.MachineLearningServices/workspaces@2025-06-01' = {
  name: 'mlw-${prefix}'
  location: location
  tags: tags
  kind: 'Default'
  identity: { type: 'SystemAssigned' }
  properties: {
    friendlyName: 'Azure ML CPU MLOps training'
    description: 'Synthetic telco data, MLflow, SDK v2 pipelines, external tracking and HF CPU serving.'
    storageAccount: storage.id
    keyVault: vault.id
    applicationInsights: insights.id
    containerRegistry: registry.id
    publicNetworkAccess: 'Enabled'
    systemDatastoresAuthMode: 'Identity'
    managedNetwork: { isolationMode: 'Disabled' }
  }
}

var blobContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var storageContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '17d1049b-9a84-46fb-8f53-869881c3d3ab')
var keyVaultSecretsOfficer = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
var acrPush = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')

resource workspaceStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, workspace.id, storageContributor)
  scope: storage
  properties: {
    principalId: workspace.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageContributor
  }
}

resource workspaceVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, workspace.id, keyVaultSecretsOfficer)
  scope: vault
  properties: {
    principalId: workspace.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsOfficer
  }
}

resource workspaceAcrRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, workspace.id, acrPush)
  scope: registry
  properties: {
    principalId: workspace.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPush
  }
}

resource operatorBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, operatorPrincipalId, blobContributor)
  scope: storage
  properties: {
    principalId: operatorPrincipalId
    principalType: 'User'
    roleDefinitionId: blobContributor
  }
}

@description('Azure ML SDK workspace configuration, contains no credentials.')
output config object = {
  subscription_id: subscription().subscriptionId
  resource_group: resourceGroup().name
  workspace_name: workspace.name
}

@description('Azure ML Studio workspace URL.')
output studioUrl string = 'https://ml.azure.com/?wsid=${workspace.id}'

@description('Storage resource ID for scoped compute permissions.')
output storageId string = storage.id

@description('Container registry resource ID for endpoint image pulls.')
output registryId string = registry.id
