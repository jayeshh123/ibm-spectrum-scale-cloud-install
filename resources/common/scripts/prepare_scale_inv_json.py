#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright IBM Corporation 2018

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import json
import pathlib
import re
import os
import sys

# Note: Don't use socket for FQDN resolution.

SCALE_CLUSTER_DEFINITION_PATH = "/ibm-spectrum-scale-install-infra/vars/scale_clusterdefinition.json"  # TODO: FIX
CLUSTER_DEFINITION_JSON = {"scale_cluster": {},
                           "scale_callhome_params": {},
                           "node_details": [],
                           "scale_config": []}


def read_json_file(json_path):
    """ Read inventory as json file """
    tf_inv = {}
    try:
        with open(json_path) as json_handler:
            try:
                tf_inv = json.load(json_handler)
            except json.decoder.JSONDecodeError:
                print("Provided terraform inventory file (%s) is not a valid "
                      "json." % json_path)
                sys.exit(1)
    except OSError:
        print("Provided terraform inventory file (%s) does not exist." % json_path)
        sys.exit(1)

    return tf_inv


def calculate_pagepool(memory_size, max_pagepool_gb):
    """ Calculate pagepool (min: 4G,1/3RAM) """
    # 1 MiB = 1.048576 MB
    mem_size_mb = int(int(memory_size) * 1.048576)
    # 1 MB = 0.001 GB
    mem_size_gb = int(mem_size_mb * 0.001)
    pagepool_gb = max(round(int(mem_size_gb*33.33*0.01)), 4)
    if pagepool_gb > int(max_pagepool_gb):
        pagepool = int(max_pagepool_gb)
    else:
        pagepool = pagepool_gb
    return "{}G".format(pagepool)


def initialize_cluster_details(scale_version, cluster_name, username,
                               password, scale_profile_path,
                               scale_replica_config, bastion_ip,
                               bastion_key_file, bastion_user):
    """ Initialize cluster details.
    :args: cluster_name (string), scale_profile_file (string), scale_replica_config (bool)
    """
    CLUSTER_DEFINITION_JSON['scale_cluster']['setuptype'] = "cloud"
    CLUSTER_DEFINITION_JSON['scale_cluster']['enable_perf_reconfig'] = False
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_falpkg_install'] = False
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_version'] = scale_version
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_gui_admin_user'] = username
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_gui_admin_password'] = password
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_gui_admin_role'] = "Administrator"

    CLUSTER_DEFINITION_JSON['scale_cluster']['ephemeral_port_range'] = "60000-61000"
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_cluster_clustername'] = cluster_name
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_service_gui_start'] = True
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_sync_replication_config'] = scale_replica_config
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_cluster_profile_name'] = str(
        pathlib.PurePath(scale_profile_path).stem)
    CLUSTER_DEFINITION_JSON['scale_cluster']['scale_cluster_profile_dir_path'] = str(
        pathlib.PurePath(scale_profile_path).parent)
    if bastion_ip is not None:
        CLUSTER_DEFINITION_JSON['scale_cluster']['scale_jump_host'] = bastion_ip
    if bastion_key_file is not None:
        CLUSTER_DEFINITION_JSON['scale_cluster']['scale_jump_host_private_key'] = bastion_key_file
    if bastion_user is not None:
        CLUSTER_DEFINITION_JSON['scale_cluster']['scale_jump_host_user'] = bastion_user


def initialize_callhome_details():
    CLUSTER_DEFINITION_JSON['scale_callhome_params']['is_enabled'] = False


def initialize_scale_config_details(node_class, param_key, param_value):
    """ Initialize cluster details.
    :args: node_class (string), param_key (string), param_value (string)
    """
    CLUSTER_DEFINITION_JSON['scale_config'].append({"nodeclass": node_class,
                                                    "params": [{param_key: param_value}]})


def set_node_details(fqdn, ip_address, ansible_ssh_private_key_file,
                     node_class, user, is_quorum_node=False,
                     is_manager_node=False, is_gui_server=False,
                     is_collector_node=False, is_nsd_server=False,
                     is_admin_node=True):
    """ Initialize node details for cluster definition.
    :args: json_data (json), fqdn (string), ip_address (string), node_class (string),
           is_nsd_server (bool), is_quorum_node (bool),
           is_manager_node (bool), is_collector_node (bool), is_gui_server (bool),
           is_admin_node (bool)
    """
    CLUSTER_DEFINITION_JSON['node_details'].append({
        'fqdn': fqdn,
        'ip_address': ip_address,
        'ansible_ssh_private_key_file': ansible_ssh_private_key_file,
        'scale_state': 'present',
        'is_nsd_server': is_nsd_server,
        'is_quorum_node': is_quorum_node,
        'is_manager_node': is_manager_node,
        'scale_zimon_collector': is_collector_node,
        'is_gui_server': is_gui_server,
        'is_admin_node': is_admin_node,
        'scale_nodeclass': node_class,
        "os": "rhel8",  # TODO: FIX
        "arch": "x86_64",  # TODO: FIX
        "is_object_store": False,
        "is_nfs": False,
        "is_smb": False,
        "is_hdfs": False,
        "is_protocol_node": False,
        "is_ems_node": False,
        "is_callhome_node": False,
        "is_broker_node": False,
        "is_node_offline": False,
        "is_node_reachable": True,
        "is_node_excluded": False,
        "is_mestor_node": False,
        "scale_daemon_nodename": fqdn,
        "upgrade_prompt": False
    })


def interleave_nodes_by_fg(node_details):
    failure_groups = {}
    zone_list = []
    for node in node_details:
        ip = node['private_ip']
        zone = node['zone']
        if zone not in failure_groups:
            failure_groups[zone] = []
            zone_list.append(zone)
        failure_groups[zone].append(ip)

    instances = []
    max_len = max(len(nodes) for nodes in failure_groups.values())
    for idx in range(max_len):
        for zone in zone_list:
            nodes = failure_groups[zone]
            if idx < len(nodes):
                instances.append(nodes[idx])
    return instances


def initialize_node_details(az_count, cls_type,
                            compute_cluster_details, storage_cluster_details,
                            storage_cluster_desc_details, quorum_count, user, key_file):
    """ Initialize node details for cluster definition.
    :args: az_count (int), cls_type (string), compute_cluster_details (dict),
           storage_cluster_details (dict), storage_cluster_desc_details (dict),
           quorum_count (int), user (string), key_file (string)
    """
    node_details = []
    if cls_type == 'compute':
        start_quorum_assign = quorum_count - 1
        compute_instances = (interleave_nodes_by_fg(compute_cluster_details)
                             if az_count > 1
                             else [item["private_ip"] for item in compute_cluster_details])

        for index, each_ip in enumerate(compute_instances):
            if index <= start_quorum_assign and index <= (manager_count - 1):
                if index == 0:
                    set_node_details(compute_cluster_details[index]["dns"],
                                     each_ip, key_file, "computenodegrp", user,
                                     is_quorum_node=True, is_manager_node=True,
                                     is_gui_server=True, is_collector_node=True,
                                     is_nsd_server=False, is_admin_node=True)
                elif index == 1:
                    set_node_details(compute_cluster_details[index]["dns"], each_ip,
                                     key_file, "computenodegrp", user,
                                     is_quorum_node=True, is_manager_node=True,
                                     is_gui_server=False, is_collector_node=True,
                                     is_nsd_server=False, is_admin_node=False)
                else:
                    set_node_details(compute_cluster_details[index]["dns"], each_ip,
                                     key_file, "computenodegrp", user,
                                     is_quorum_node=True, is_manager_node=True,
                                     is_gui_server=False, is_collector_node=False,
                                     is_nsd_server=False, is_admin_node=False)
            elif index <= start_quorum_assign and index > (manager_count - 1):
                set_node_details(compute_cluster_details[index]["dns"], each_ip,
                                 key_file, "computenodegrp", user,
                                 is_quorum_node=True, is_manager_node=False,
                                 is_gui_server=False, is_collector_node=False,
                                 is_nsd_server=False, is_admin_node=False)
            else:
                set_node_details(compute_cluster_details[index]["dns"], each_ip,
                                 key_file, "computenodegrp", user,
                                 is_quorum_node=False, is_manager_node=False,
                                 is_gui_server=False, is_collector_node=False,
                                 is_nsd_server=False, is_admin_node=False)

    elif cls_type == 'storage':
        if az_count == 1:
            # Storage/NSD nodes to be quorum nodes (quorum_count - 1 as index starts from 0)
            start_quorum_assign = quorum_count - 1
            storage_instances = [item["private_ip"]
                                 for item in storage_cluster_details]
            for index, each_ip in enumerate(storage_instances):
                if index <= start_quorum_assign and index <= (manager_count - 1):
                    if index == 0:
                        set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                         key_file, "storagenodegrp", user,
                                         is_quorum_node=True, is_manager_node=True,
                                         is_gui_server=True, is_collector_node=True,
                                         is_nsd_server=True, is_admin_node=True)
                    elif index == 1:
                        set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                         key_file, "storagenodegrp", user,
                                         is_quorum_node=True, is_manager_node=True,
                                         is_gui_server=False, is_collector_node=True,
                                         is_nsd_server=True, is_admin_node=False)
                    else:
                        set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                         key_file, "storagenodegrp", user,
                                         is_quorum_node=True, is_manager_node=False,
                                         is_gui_server=False, is_collector_node=False,
                                         is_nsd_server=True, is_admin_node=False)
                elif index <= start_quorum_assign and index > (manager_count - 1):
                    set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                     key_file, "storagenodegrp", user,
                                     is_quorum_node=True, is_manager_node=False,
                                     is_gui_server=False, is_collector_node=False,
                                     is_nsd_server=True, is_admin_node=False)
                else:
                    set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                     key_file, "storagenodegrp", user,
                                     is_quorum_node=False, is_manager_node=False,
                                     is_gui_server=False, is_collector_node=False,
                                     is_nsd_server=True, is_admin_node=False)
        elif az_count > 1:
            # Storage/NSD nodes to be quorum nodes (quorum_count - 2 as index starts from 0)
            start_quorum_assign = quorum_count - 2
            storage_desc_instances = [item["private_ip"]
                                      for item in storage_cluster_desc_details]
            for index, each_ip in enumerate(storage_desc_instances):
                set_node_details(storage_cluster_desc_details[index]["dns"], each_ip,
                                 key_file, "computedescnodegrp", user,
                                 is_quorum_node=True, is_manager_node=False,
                                 is_gui_server=False, is_collector_node=False,
                                 is_nsd_server=True, is_admin_node=False)

            storage_instances = interleave_nodes_by_fg(
                storage_cluster_details)
            for index, each_ip in enumerate(storage_instances):
                if index <= start_quorum_assign and index <= (manager_count - 1):
                    if index == 0:
                        set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                         key_file, "storagenodegrp", user,
                                         is_quorum_node=True, is_manager_node=True,
                                         is_gui_server=True, is_collector_node=True,
                                         is_nsd_server=True, is_admin_node=True)
                    elif index == 1:
                        set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                         key_file, "storagenodegrp", user,
                                         is_quorum_node=True, is_manager_node=True,
                                         is_gui_server=False, is_collector_node=True,
                                         is_nsd_server=True, is_admin_node=True)
                    else:
                        set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                         key_file, "storagenodegrp", user,
                                         is_quorum_node=True, is_manager_node=True,
                                         is_gui_server=False, is_collector_node=False,
                                         is_nsd_server=True, is_admin_node=True)
                elif index <= start_quorum_assign and index > (manager_count - 1):
                    set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                     key_file, "storagenodegrp", user,
                                     is_quorum_node=True, is_manager_node=False,
                                     is_gui_server=False, is_collector_node=False,
                                     is_nsd_server=True, is_admin_node=True)
                else:
                    set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                     key_file, "storagenodegrp", user,
                                     is_quorum_node=False, is_manager_node=False,
                                     is_gui_server=False, is_collector_node=False,
                                     is_nsd_server=True, is_admin_node=False)

    elif cls_type == 'combined':
        storage_desc_instances = [item["private_ip"]
                                  for item in storage_cluster_desc_details]
        for index, each_ip in enumerate(storage_desc_instances):
            set_node_details(storage_cluster_desc_details[index]["dns"], each_ip,
                             key_file, "computedescnodegrp", user,
                             is_quorum_node=True, is_manager_node=False,
                             is_gui_server=False, is_collector_node=False,
                             is_nsd_server=True, is_admin_node=False)

        if az_count > 1:
            # Storage/NSD nodes to be quorum nodes (quorum_count - 2 as index starts from 0)
            start_quorum_assign = quorum_count - 2
            storage_instances = interleave_nodes_by_fg(storage_cluster_details)
        else:
            # Storage/NSD nodes to be quorum nodes (quorum_count - 1 as index starts from 0)
            start_quorum_assign = quorum_count - 1
            storage_instances = [item["private_ip"]
                                 for item in storage_cluster_details]

        for index, each_ip in enumerate(storage_instances):
            if index <= start_quorum_assign and index <= (manager_count - 1):
                if index == 0:
                    set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                     key_file, "storagenodegrp", user,
                                     is_quorum_node=True, is_manager_node=True,
                                     is_gui_server=True, is_collector_node=True,
                                     is_nsd_server=True, is_admin_node=True)
                elif index == 1:
                    set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                     key_file, "storagenodegrp", user,
                                     is_quorum_node=True, is_manager_node=True,
                                     is_gui_server=False, is_collector_node=True,
                                     is_nsd_server=True, is_admin_node=True)
                else:
                    set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                     key_file, "storagenodegrp", user,
                                     is_quorum_node=True, is_manager_node=True,
                                     is_gui_server=False, is_collector_node=False,
                                     is_nsd_server=True, is_admin_node=True)
            elif index <= start_quorum_assign and index > (manager_count - 1):
                set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                 key_file, "storagenodegrp", user,
                                 is_quorum_node=True, is_manager_node=False,
                                 is_gui_server=False, is_collector_node=False,
                                 is_nsd_server=True, is_admin_node=True)
            else:
                set_node_details(storage_cluster_details[index]["dns"], each_ip,
                                 key_file, "storagenodegrp", user,
                                 is_quorum_node=False, is_manager_node=False,
                                 is_gui_server=False, is_collector_node=False,
                                 is_nsd_server=True, is_admin_node=False)

        if az_count > 1:
            if len([item["private_ip"] for item in storage_cluster_details]) - len([item["private_ip"] for item in storage_cluster_desc_details]) >= quorum_count:
                quorums_left = 0
            else:
                quorums_left = quorum_count - \
                    len([item["private_ip"] for item in storage_cluster_details]) - \
                    len([item["private_ip"]
                        for item in storage_cluster_desc_details])
        else:
            if len([item["private_ip"] for item in storage_cluster_details]) > quorum_count:
                quorums_left = 0
            else:
                quorums_left = quorum_count - \
                    len([item["private_ip"]
                        for item in storage_cluster_details])

        # Additional quorums assign to compute nodes
        if quorums_left > 0:
            compute_instances = interleave_nodes_by_fg(compute_cluster_details)
            for each_instance in compute_instances[0:quorums_left]:
                set_node_details(each_instance["dns"], each_instance["private_ip"],
                                 key_file, "computenodegrp", user,
                                 is_quorum_node=True, is_manager_node=False,
                                 is_gui_server=False, is_collector_node=False,
                                 is_nsd_server=False, is_admin_node=True)

            for each_instance in compute_instances[quorums_left:]:
                set_node_details(each_instance["dns"], each_instance["private_ip"],
                                 key_file, "computenodegrp", user,
                                 is_quorum_node=False, is_manager_node=False,
                                 is_gui_server=False, is_collector_node=False,
                                 is_nsd_server=False, is_admin_node=False)

        if quorums_left == 0:
            compute_instances = (interleave_nodes_by_fg(compute_cluster_details)
                                 if az_count > 1
                                 else [item["private_ip"] for item in compute_cluster_details])

            for index, each_ip in enumerate(compute_instances):
                set_node_details(compute_cluster_details[index]["dns"], each_ip,
                                 key_file, "computenodegrp", user,
                                 is_quorum_node=False, is_manager_node=False,
                                 is_gui_server=False, is_collector_node=False,
                                 is_nsd_server=False, is_admin_node=False)
    return node_details


def get_disks_list(data_disk_map, desc_disk_map):
    """ Initialize disk list. """

    zones_ip_map = {}
    # Map zones to failure groups
    for each_ip, disk_details in data_disk_map.items():
        zone = disk_details["zone"]
        if zone not in zones_ip_map:
            zones_ip_map[zone] = []
        zones_ip_map[zone].append(each_ip)

    failure_group1, failure_group2 = [], []
    zones = list(zones_ip_map.keys())
    if len(zones) == 1:
        # Single AZ, just split list equally
        num_storage_nodes = len(zones_ip_map[zones[0]])
        print(num_storage_nodes)
        mid_index = num_storage_nodes//2
        failure_group1 = zones_ip_map[zones[0]][:mid_index]
        failure_group2 = zones_ip_map[zones[0]][mid_index:]
    else:
        # Multi AZ, split based on keys
        failure_group1 = zones_ip_map[zones[0]]
        failure_group2 = zones_ip_map[zones[1]]

    # Prepare dict of disks / NSD list
    # "nsd": "nsd1",
    # "device": "/dev/xvdf",
    # "size": 536870912000,
    # "failureGroup": "1",
    # "filesystem": "FS1",
    # "servers": "ip-10-0-3-10.ap-south-1.compute.internal",
    # "usage": "dataAndMetadata",
    # "pool": "system"

    disks_list = []
    for each_ip, disk_details in data_disk_map.items():
        if each_ip in failure_group1:
            for _, each_disk in disk_details["disks"].items():
                # disks_list.append({"device": each_disk,
                #                    "failureGroup": 1, "servers": each_ip,
                #                    "usage": "dataAndMetadata", "pool": "system"})

                # TODO: FIX Include disk "size"
                disks_list.append({
                    "nsd": "nsd_" + each_ip.replace(".", "_") + "_" + os.path.basename(each_disk["device_name"]),
                    "filesystem": each_disk["fs_name"],
                    "device": each_disk["device_name"],
                    "failureGroup": 1,
                    "servers": each_ip,
                    "usage": "dataAndMetadata",
                    "pool": each_disk["pool"]
                })

        if each_ip in failure_group2:
            for _, each_disk in disk_details["disks"].items():
                # disks_list.append({"device": each_disk,
                #                    "failureGroup": 2, "servers": each_ip,
                #                    "usage": "dataAndMetadata", "pool": "system"})

                # TODO: FIX Include disk "size"
                disks_list.append({
                    "nsd": "nsd_" + each_ip.replace(".", "_") + "_" + os.path.basename(each_disk["device_name"]),
                    "filesystem": each_disk["fs_name"],
                    "device": each_disk["device_name"],
                    "failureGroup": 2,
                    "servers": each_ip,
                    "usage": "dataAndMetadata",
                    "pool": each_disk["pool"]
                })

    # Append "descOnly" disk details
    if len(desc_disk_map.keys()):
        for each_ip, disk_details in desc_disk_map.items():
            for _, each_disk in disk_details["disks"].items():
                disks_list.append({
                    "nsd": "nsd_" + each_ip.replace(".", "_") + "_" + os.path.basename(each_disk["device_name"]),
                    "filesystem": each_disk["fs_name"],
                    "device": each_disk["device_name"],
                    "failureGroup": 3,
                    "servers": each_ip,
                    "usage": "descOnly",
                    "pool": each_disk["pool"]
                })

    return disks_list


def initialize_scale_storage_details(fs_details):
    """ Initialize storage details."""

    # "scale_filesystem": [
    #    {
    #        "filesystem": "FS1",
    #        "defaultMountPoint": "/ibm/FS1",
    #        "blockSize": "4M",
    #        "defaultDataReplicas": "1",
    #        "maxDataReplicas": "2",
    #        "defaultMetadataReplicas": "1",
    #        "maxMetadataReplicas": "2",
    #        "scale_fal_enable": "False",
    #        "logfileset": ".audit_log",
    #        "retention": "365"
    #    }
    # ]

    storage = []
    for fs_name, fs_config in fs_details.items():
        with open(fs_config, 'r') as file:
            fs_data = json.load(file)
            storage.append({"filesystem": fs_name,
                            "defaultMountPoint": fs_data["filesystem_config_params"][fs_name]["mount_point"],
                            "blockSize": fs_data["filesystem_config_params"][fs_name]["block_size"],
                            "defaultDataReplicas": fs_data["filesystem_config_params"][fs_name]["data_replicas"],
                            "maxDataReplicas": fs_data["filesystem_config_params"][fs_name]["max_data_replicas"],
                            "defaultMetadataReplicas": fs_data["filesystem_config_params"][fs_name]["metadata_replicas"],
                            "maxMetadataReplicas": fs_data["filesystem_config_params"][fs_name]["max_metadata_replicas"],
                            "scale_fal_enable": False,
                            "logfileset": ".audit_log",
                            "automaticMountOption": True,
                            "retention": "365"
                            })

    return storage


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser(description='Convert terraform inventory '
                                                 'to ansible inventory format '
                                                 'install and configuration.')
    PARSER.add_argument('--tf_inv_path', required=True,
                        help='Terraform inventory file path')
    PARSER.add_argument('--install_infra_path', required=True,
                        help='Spectrum Scale install infra clone parent path')
    PARSER.add_argument('--instance_private_key', required=True,
                        help='Spectrum Scale instances SSH private key path')
    PARSER.add_argument('--bastion_user',
                        help='Bastion OS Login username')
    PARSER.add_argument('--bastion_ip',
                        help='Bastion SSH public ip address')
    PARSER.add_argument('--bastion_ssh_private_key',
                        help='Bastion SSH private key path')
    PARSER.add_argument('--memory_size', help='Instance memory size')
    PARSER.add_argument('--max_pagepool_gb', help='maximum pagepool size in GB',
                        default=4)
    PARSER.add_argument('--using_packer_image', help='skips gpfs rpm copy')
    PARSER.add_argument('--using_rest_initialization',
                        help='skips gui configuration')
    PARSER.add_argument('--gui_username', required=True,
                        help='Spectrum Scale GUI username')
    PARSER.add_argument('--gui_password', required=True,
                        help='Spectrum Scale GUI password')
    PARSER.add_argument('--disk_type', help='Disk type')
    PARSER.add_argument('--enable_mrot_conf', required=True)
    PARSER.add_argument('--verbose', action='store_true',
                        help='print log messages')

    ARGUMENTS = PARSER.parse_args()

    # Step-1: Read the inventory file
    TF = read_json_file(ARGUMENTS.tf_inv_path)

    if ARGUMENTS.verbose:
        print("Parsed terraform output: %s" % json.dumps(TF, indent=4))

    # Step-2: Identify the cluster type
    if len([item["private_ip"] for item in TF['storage_cluster_details']]) == 0 and \
       len([item["private_ip"] for item in TF['compute_cluster_details']]) > 0:
        cluster_type = "compute"
        gui_username = ARGUMENTS.gui_username
        gui_password = ARGUMENTS.gui_password
        profile_path = "%s/computesncparams" % ARGUMENTS.install_infra_path
        replica_config = False
        pagepool_size = calculate_pagepool(ARGUMENTS.memory_size,
                                           ARGUMENTS.max_pagepool_gb)
        scale_config = initialize_scale_config_details("computenodegrp",
                                                       "pagepool",
                                                       pagepool_size)
    elif len([item["private_ip"] for item in TF['compute_cluster_details']]) == 0 and \
            len([item["private_ip"] for item in TF['storage_cluster_details']]) > 0 and \
            len(TF['vpc_availability_zones']) == 1:
        # single az storage cluster
        cluster_type = "storage"
        gui_username = ARGUMENTS.gui_username
        gui_password = ARGUMENTS.gui_password
        profile_path = "%s/storagesncparams" % ARGUMENTS.install_infra_path
        replica_config = bool(len(TF['vpc_availability_zones']) > 1)
        pagepool_size = calculate_pagepool(ARGUMENTS.memory_size,
                                           ARGUMENTS.max_pagepool_gb)
        scale_config = initialize_scale_config_details("storagenodegrp",
                                                       "pagepool",
                                                       pagepool_size)
    elif len([item["private_ip"] for item in TF['compute_cluster_details']]) == 0 and \
            len([item["private_ip"] for item in TF['storage_cluster_details']]) > 0 and \
            len(TF['vpc_availability_zones']) > 1 and \
            len([item["private_ip"] for item in TF['storage_cluster_desc_details']]) > 0:
        # multi az storage cluster
        cluster_type = "storage"
        gui_username = ARGUMENTS.gui_username
        gui_password = ARGUMENTS.gui_password
        profile_path = "%s/storagesncparams" % ARGUMENTS.install_infra_path
        replica_config = bool(len(TF['vpc_availability_zones']) > 1)
        pagepool_size = calculate_pagepool(ARGUMENTS.memory_size,
                                           ARGUMENTS.max_pagepool_gb)
        scale_config = initialize_scale_config_details("storagenodegrp",
                                                       "pagepool",
                                                       pagepool_size)
        scale_config = initialize_scale_config_details("computedescnodegrp",
                                                       "pagepool",
                                                       pagepool_size)
    else:
        cluster_type = "combined"
        gui_username = ARGUMENTS.gui_username
        gui_password = ARGUMENTS.gui_password
        profile_path = "%s/scalesncparams" % ARGUMENTS.install_infra_path
        replica_config = bool(len(TF['vpc_availability_zones']) > 1)
        pagepool_size = calculate_pagepool(
            ARGUMENTS.memory_size, ARGUMENTS.max_pagepool_gb)
        if len(TF['vpc_availability_zones']) == 1:
            scale_config = initialize_scale_config_details(
                "storagenodegrp", "pagepool", pagepool_size)
            scale_config = initialize_scale_config_details(
                "computenodegrp", "pagepool", pagepool_size)
        else:
            scale_config = initialize_scale_config_details(
                "storagenodegrp", "pagepool", pagepool_size)
            scale_config = initialize_scale_config_details(
                "computenodegrp", "pagepool", pagepool_size)
            scale_config = initialize_scale_config_details(
                "computedescnodegrp", "pagepool", pagepool_size)

    print("Identified cluster type: %s" % cluster_type)

    # Step-3: Identify if tie breaker needs to be counted for storage
    if len(TF['vpc_availability_zones']) > 1:
        total_node_count = len([item["private_ip"] for item in TF['compute_cluster_details']]) + \
            len([item["private_ip"] for item in TF['storage_cluster_details']]) + \
            len([item["private_ip"]
                for item in TF['storage_cluster_desc_details']])
    else:
        total_node_count = len([item["private_ip"] for item in TF['compute_cluster_details']]) + \
            len([item["private_ip"] for item in TF['storage_cluster_details']])

    if ARGUMENTS.verbose:
        print("Total node count: ", total_node_count)

    # Determine total number of quorum, manager nodes to be in the cluster
    # manager designates the node as part of the pool of nodes from which
    # file system managers and token managers are selected.
    quorum_count, manager_count = 0, 2
    if total_node_count < 4:
        quorum_count = total_node_count
    elif 4 <= total_node_count < 10:
        quorum_count = 3
    elif 10 <= total_node_count < 19:
        quorum_count = 5
    else:
        quorum_count = 7

    if ARGUMENTS.verbose:
        print("Total quorum count: ", quorum_count)

    # Define cluster details
    if TF['resource_prefix']:
        cluster_name = TF['resource_prefix']
    else:
        cluster_name = "%s.%s" % ("spectrum-scale", cluster_type)

    initialize_cluster_details(TF['scale_version'],
                               cluster_name,
                               gui_username,
                               gui_password,
                               profile_path,
                               replica_config,
                               ARGUMENTS.bastion_ip,
                               ARGUMENTS.bastion_ssh_private_key,
                               ARGUMENTS.bastion_user)

    initialize_callhome_details()

    # Step-5: Create hosts
    initialize_node_details(len(TF['vpc_availability_zones']), cluster_type,
                            TF['compute_cluster_details'],
                            TF['storage_cluster_details'],
                            TF['storage_cluster_desc_details'],
                            quorum_count, "root", ARGUMENTS.instance_private_key)

    if cluster_type in ['storage', 'combined']:
        disks_list = get_disks_list(TF['storage_cluster_with_data_volume_mapping'],
                                    TF['storage_cluster_desc_data_volume_mapping'])
        scale_storage = initialize_scale_storage_details(
            TF['filesystem_details'])

        CLUSTER_DEFINITION_JSON.update({"scale_filesystem": scale_storage})
        CLUSTER_DEFINITION_JSON.update({"scale_disks": disks_list})

    if ARGUMENTS.verbose:
        print("Content of scale_clusterdefinition.json: ",
              json.dumps(CLUSTER_DEFINITION_JSON, indent=4))

    # Write json content
    if ARGUMENTS.verbose:
        print("Writing cloud infrastructure details to: ",
              ARGUMENTS.install_infra_path.rstrip('/') + SCALE_CLUSTER_DEFINITION_PATH)

    # Remove cluster definition file if it already exists
    if os.path.exists(ARGUMENTS.install_infra_path.rstrip('/') + SCALE_CLUSTER_DEFINITION_PATH):
        os.remove(ARGUMENTS.install_infra_path.rstrip(
            '/') + SCALE_CLUSTER_DEFINITION_PATH)

    # Create vars directory if missing
    if not os.path.exists(ARGUMENTS.install_infra_path.rstrip('/') + SCALE_CLUSTER_DEFINITION_PATH):
        os.makedirs(os.path.dirname(ARGUMENTS.install_infra_path.rstrip(
            '/') + SCALE_CLUSTER_DEFINITION_PATH), exist_ok=True)

    with open(ARGUMENTS.install_infra_path.rstrip('/') + SCALE_CLUSTER_DEFINITION_PATH, 'w') as json_fh:
        json.dump(CLUSTER_DEFINITION_JSON, json_fh, indent=4)

    if ARGUMENTS.verbose:
        print("Completed writing cloud infrastructure details to: ",
              ARGUMENTS.install_infra_path.rstrip('/') + SCALE_CLUSTER_DEFINITION_PATH)
