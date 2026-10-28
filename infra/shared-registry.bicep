metadata name = 'KT shared Azure ML Registry'
metadata description = 'Versioned ML assets shared between independent team workspaces; not a container registry.'

@description('Registry region, shared by producer and consumer workspaces.')
param location string = resourceGroup().location

@description('Globally unique Azure ML Registry name.')
param registryName string

resource registry 'Microsoft.MachineLearningServices/registries@2025-06-01' = {
  name: registryName
  location: location
  identity: { type: 'SystemAssigned' }
  tags: {
    project: 'azure-llm-mlops'
    purpose: 'training-demo'
    dataClassification: 'synthetic'
    team: 'shared'
    costCenter: 'kt-mlops-shared'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    regionDetails: [
      {
        location: location
        storageAccountDetails: [
          { systemCreatedStorageAccount: { storageAccountType: 'Standard_LRS' } }
        ]
        acrDetails: [
          { systemCreatedAcrAccount: { acrAccountSku: 'Premium' } }
        ]
      }
    ]
  }
}

@description('Shared Registry ARM ID for narrowly scoped consumer read access.')
output registryId string = registry.id
