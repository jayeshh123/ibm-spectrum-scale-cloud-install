/*
  Creates GCP VM instance with additional(Persistent/Ephemeral) disks (i.e. storage instances)
*/

variable "vpc_region" {}
variable "zone" {}
variable "subnet_name" {}
variable "disk" {}
variable "total_local_ssd_disks" {}
variable "is_multizone" {}
variable "instance_name" {}
variable "machine_type" {}
variable "boot_disk_size" {}
variable "boot_disk_type" {}
variable "boot_image" {}
variable "ssh_user_name" {}
variable "ssh_public_key_path" {}
variable "data_disk_description" {}
variable "physical_block_size_bytes" {}
variable "private_key_content" {}
variable "public_key_content" {}
variable "vpc_forward_dns_zone" {}
variable "vpc_dns_domain" {}
variable "vpc_reverse_dns_zone" {}
variable "vpc_reverse_dns_domain" {}
variable "root_device_kms_key_ring_ref" {}
variable "root_device_kms_key_ref" {}
variable "service_email" {}
variable "scopes" {}
variable "network_tags" {}

data "google_kms_key_ring" "itself" {
  count    = var.root_device_kms_key_ring_ref != null ? 1 : 0
  name     = var.root_device_kms_key_ring_ref
  location = var.vpc_region
}

data "google_kms_crypto_key" "itself" {
  count    = var.root_device_kms_key_ref != null && var.root_device_kms_key_ring_ref != null ? 1 : 0
  name     = var.root_device_kms_key_ref
  key_ring = data.google_kms_key_ring.itself[0].id
}

data "template_file" "metadata_startup_script" {
  template = <<EOF
#!/usr/bin/env bash
echo "${var.private_key_content}" > ~/.ssh/id_rsa
chmod 600 ~/.ssh/id_rsa
echo "${var.public_key_content}" >> ~/.ssh/authorized_keys
echo "StrictHostKeyChecking no" >> ~/.ssh/config
EOF
}

#tfsec:ignore:google-compute-enable-shielded-vm-im
#tfsec:ignore:google-compute-enable-shielded-vm-vtpm
#tfsec:ignore:google-compute-vm-disk-encryption-customer-key
resource "google_compute_instance" "itself" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone
  hostname     = format("%s.%s", var.instance_name, var.vpc_dns_domain)

  allow_stopping_for_update = true

  #tfsec:ignore:google-compute-vm-disk-encryption-customer-key
  boot_disk {
    auto_delete = true
    mode        = "READ_WRITE"

    initialize_params {
      size  = var.boot_disk_size
      type  = var.boot_disk_type
      image = var.boot_image
    }
    kms_key_self_link = length(data.google_kms_crypto_key.itself) > 0 ? data.google_kms_crypto_key.itself[0].id : null
  }

  network_interface {
    subnetwork = var.subnet_name
    network_ip = null
  }
  tags = var.network_tags

  # Block for scratch/local-ssd disk attachment
  dynamic "scratch_disk" {
    for_each = range(var.total_local_ssd_disks)
    content {
      interface = "NVME"
    }
  }

  metadata = {
    ssh-keys               = format("%s:%s", var.ssh_user_name, file(var.ssh_public_key_path))
    block-project-ssh-keys = true
    vmdnssetting           = var.is_multizone ? "GlobalDefault" : "ZonalOnly"
  }

  metadata_startup_script = data.template_file.metadata_startup_script.rendered

  service_account {
    email  = var.service_email
    scopes = var.scopes
  }

  lifecycle {
    ignore_changes = all
  }
}

# Add the VM instance ip as 'A' record to DNS
resource "google_dns_record_set" "a_itself" {
  name         = format("%s.%s.", google_compute_instance.itself.name, var.vpc_dns_domain) # Trailing dot is required
  type         = "A"
  managed_zone = var.vpc_forward_dns_zone
  ttl          = 300
  rrdatas      = [google_compute_instance.itself.network_interface[0].network_ip]
}

# Add the VM instance reverse lookup as 'PTR' record to DNS
resource "google_dns_record_set" "ptr_itself" {
  name         = format("%s.%s.%s.%s.", split(".", google_compute_instance.itself.network_interface[0].network_ip)[3], split(".", google_compute_instance.itself.network_interface[0].network_ip)[2], split(".", google_compute_instance.itself.network_interface[0].network_ip)[1], var.vpc_reverse_dns_domain) # Trailing dot is required
  type         = "PTR"
  managed_zone = var.vpc_reverse_dns_zone
  ttl          = 300
  rrdatas      = [format("%s.%s.", google_compute_instance.itself.name, var.vpc_dns_domain)] # Trailing dot is required
}

data "google_kms_key_ring" "data_device_key_ring" {
  for_each = { for disk_key, disk_config in var.disk : disk_key => disk_config["kms_key_ring"] if disk_config["kms_key"] != null }
  name     = each.value
  location = var.vpc_region
}

data "google_kms_crypto_key" "data_device_kms_key" {
  for_each = { for disk_key, disk_config in var.disk : disk_key => disk_config["kms_key"] if disk_config["kms_key_ring"] != null }
  name     = each.value
  key_ring = data.google_kms_key_ring.data_device_key_ring[each.key].id
}

#tfsec:ignore:google-compute-vm-disk-encryption-customer-key
resource "google_compute_disk" "itself" {
  for_each                  = var.disk
  name                      = each.key
  zone                      = var.zone
  description               = var.data_disk_description
  physical_block_size_bytes = var.physical_block_size_bytes
  type                      = each.value["type"]
  size                      = each.value["size"]
  dynamic "disk_encryption_key" {
    for_each = each.value["kms_key"] != null ? [1] : []
    content {
      kms_key_self_link = data.google_kms_crypto_key.data_device_kms_key[each.key].self_link
    }
  }
}

resource "google_compute_attached_disk" "itself" {
  for_each    = google_compute_disk.itself
  disk        = each.key
  device_name = each.key
  instance    = google_compute_instance.itself.id
  mode        = "READ_WRITE"
}

# Ex: id: projects/spectrum-scale-xyz/zones/us-central1-b/instances/test-compute-2,  regex o/p: test-compute-2
output "instance_details" {
  value = {
    private_ip = google_compute_instance.itself.network_interface[0].network_ip
    id         = google_compute_instance.itself.id
    dns        = format("%s.%s", regex("^projects/[^/]+/zones/[^/]+/instances/([^/]+)$", google_compute_instance.itself.id)[0], var.vpc_dns_domain)
    zone       = regex("^projects/[^/]+/zones/([^/]+)/instances/.*$", google_compute_instance.itself.id)[0]
  }
}