# Configure Azure Bastion Service

Deploys Bastion/Jump Host for IBM Storage Scale cluster.

Azure offers a Fully Managed RDP/SSH bastion service, which can be provisioned via azure_bastion_service variable.

Below steps will provision Bastion host required for IBM Storage Scale cloud solution.

1. Change working directory to `azure_scale_templates/sub_modules/bastion_template`.

    ```cli
    cd ibm-spectrum-scale-cloud-install/azure_scale_templates/sub_modules/bastion_template/
    ```

2. Create terraform variable definitions file (`terraform.tfvars.json`) and provide infrastructure inputs.

    Minimal Example:

    ```jsonc
        {
            "client_id": "xxxx1ee24-5f02-4066-b3b7-xxxxxxxxxx",
            "client_secret": "xxxxxxwiywnrm.FaqwZxxxxxxxxxxxx",
            "subscription_id": "xxx3cd6f-667b-4a89-a046-dexxxxxxxx",
            "tenant_id": "xxxx057-50c9-4ad4-98f3-xxxxxx",
            "vpc_region": "eastus",
            "vpc_ref": "storage-scale-vpc",
            "resource_prefix": "production01",
            "vpc_auto_scaling_group_subnets": [
                "/subscriptions/xxx3cd6f-667b-4a89-a046-dexxxxxxxx/resourceGroups/storage-scale-rg/providers/Microsoft.Network/virtualNetworks/storage-scale-vpc/subnets/AzureBastionSubnet-0"
            ],
            "resource_group_name": "storage-scale",
            "bastion_ssh_key_path": "/root/.ssh/id_rsa.pub",
            "os_storage_account_type": "Standard_LRS",
            "vpc_bastion_service_subnets_cidr_blocks": [
                "10.0.5.0/24"
            ],
            "remote_cidr_blocks": [
                "52.1.XX.XX/20"
            ],
            "azure_bastion_service": false,
            "image_publisher": "Canonical",
            "image_offer": "0001-com-ubuntu-server-jammy",
            "image_sku": "22_04-lts-gen2",
            "bastion_instance_type": "Standard_DS1_v2",
            "bastion_login_username": "azureuser"
        }
    ```

3. Run `terraform init` and `terraform apply -auto-approve` to provision resources.

<!-- BEGIN_TF_DOCS -->
#### Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement_terraform) | ~> 1.3 |
| <a name="requirement_azurerm"></a> [azurerm](#requirement_azurerm) | ~> 3.0 |

#### Inputs

| Name | Description | Type |
|------|-------------|------|
| <a name="input_azure_bastion_service"></a> [azure_bastion_service](#input_azure_bastion_service) | Enable Azure Bastion service | `bool` |
| <a name="input_bastion_boot_disk_type"></a> [bastion_boot_disk_type](#input_bastion_boot_disk_type) | Type of storage account which should back this the internal OS disk (Ex: Standard_LRS, StandardSSD_LRS and Premium_LRS). | `string` |
| <a name="input_bastion_instance_type"></a> [bastion_instance_type](#input_bastion_instance_type) | Instance type to use for provisioning the compute cluster instances. | `string` |
| <a name="input_bastion_ssh_key_path"></a> [bastion_ssh_key_path](#input_bastion_ssh_key_path) | SSH public key local path, will be used to login bastion instance. | `string` |
| <a name="input_bastion_ssh_user_name"></a> [bastion_ssh_user_name](#input_bastion_ssh_user_name) | The Bastion SSH username to launch bastion vm. | `string` |
| <a name="input_client_id"></a> [client_id](#input_client_id) | The Active Directory service principal associated with your account. | `string` |
| <a name="input_client_secret"></a> [client_secret](#input_client_secret) | The password or secret for your service principal. | `string` |
| <a name="input_image_offer"></a> [image_offer](#input_image_offer) | Specifies the offer of the image used to create the storage cluster virtual machines. | `string` |
| <a name="input_image_publisher"></a> [image_publisher](#input_image_publisher) | Specifies the publisher of the image used to create the storage cluster virtual machines. | `string` |
| <a name="input_image_sku"></a> [image_sku](#input_image_sku) | Specifies the SKU of the image used to create the storage cluster virtual machines. | `string` |
| <a name="input_image_version"></a> [image_version](#input_image_version) | Specifies the version of the image used to create the compute cluster virtual machines. | `string` |
| <a name="input_remote_cidr_blocks"></a> [remote_cidr_blocks](#input_remote_cidr_blocks) | List of CIDRs that can access to the bastion. | `list(string)` |
| <a name="input_resource_group_name"></a> [resource_group_name](#input_resource_group_name) | The name of a new resource group in which the resources will be created. | `string` |
| <a name="input_subscription_id"></a> [subscription_id](#input_subscription_id) | The subscription ID to use. | `string` |
| <a name="input_tenant_id"></a> [tenant_id](#input_tenant_id) | The Active Directory tenant identifier, must provide when using service principals. | `string` |
| <a name="input_vpc_auto_scaling_group_subnets"></a> [vpc_auto_scaling_group_subnets](#input_vpc_auto_scaling_group_subnets) | List of IDs of bastion subnets. | `list(string)` |
| <a name="input_vpc_availability_zones"></a> [vpc_availability_zones](#input_vpc_availability_zones) | A list of availability zones ids in the region/location. | `list(string)` |
| <a name="input_vpc_network_security_group_ref"></a> [vpc_network_security_group_ref](#input_vpc_network_security_group_ref) | VNet network security group id/reference. | `string` |
| <a name="input_vpc_ref"></a> [vpc_ref](#input_vpc_ref) | VPC id to where bastion needs to deploy. | `string` |
| <a name="input_vpc_region"></a> [vpc_region](#input_vpc_region) | The location/region of the vnet to create. Examples are East US, West US, etc. | `string` |
| <a name="input_nsg_rule_start_index"></a> [nsg_rule_start_index](#input_nsg_rule_start_index) | Specifies the network security group rule priority start index. | `number` |
| <a name="input_os_disk_caching"></a> [os_disk_caching](#input_os_disk_caching) | Specifies the caching requirements for the OS Disk (Ex: None, ReadOnly and ReadWrite). | `string` |
| <a name="input_resource_prefix"></a> [resource_prefix](#input_resource_prefix) | Prefix is added to all resources that are created. | `string` |

#### Outputs

| Name | Description |
|------|-------------|
| <a name="output_bastion_instance_autoscaling_group_ref"></a> [bastion_instance_autoscaling_group_ref](#output_bastion_instance_autoscaling_group_ref) | Bastion instance id. |
| <a name="output_bastion_instance_public_ip"></a> [bastion_instance_public_ip](#output_bastion_instance_public_ip) | Bastion instance public ip address. |
| <a name="output_bastion_security_group_ref"></a> [bastion_security_group_ref](#output_bastion_security_group_ref) | Bastion network security group name. |
| <a name="output_bastion_service_instance_dns_name"></a> [bastion_service_instance_dns_name](#output_bastion_service_instance_dns_name) | Bastion instance dns name. |
| <a name="output_bastion_service_instance_id"></a> [bastion_service_instance_id](#output_bastion_service_instance_id) | Bastion service instance id. |
<!-- END_TF_DOCS -->
