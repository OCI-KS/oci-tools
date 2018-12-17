import oci
import logging
from pprint import pformat

from .oci_config import OCIConfig
from .oci_resources import *


def scan_tenancy(config:OCIConfig):
    compartment_list(config)
    resource_list(config)
    logging.info('{}'.format(pformat(config.compartments_tree)))


def compartment_list(conf:OCIConfig):
    """
    list all compartments
    """
    compartment_tree = {}

    for r in conf.regions:
        conf.workon_region=r
        compartment_tree[r]=compartment_tree_build(conf)
        logging.info('_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-')
        logging.info('Compartment tree')
        logging.info('Region: {}\n{}'.format(r,pformat(compartment_tree[r])))
        logging.info('_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-')

    conf.compartments_tree = compartment_tree


def compartment_tree_build(conf:OCIConfig):
    """
    build a full compartment tree
    """
    identity_client=oci.identity.IdentityClient(conf.config)

    elems = oci.pagination.list_call_get_all_results(identity_client.list_compartments,compartment_id=conf.tenancy,compartment_id_in_subtree=True)
    elem_with_children = {}

    def _build_children_sub_tree(parent,name):
          cur_dict = {
              'name': name,
              'id': parent,
          }
          if parent in elem_with_children.keys():
              cur_dict["nested"] = [_build_children_sub_tree(cid[0],cid[1]) for cid in elem_with_children[parent]]
          return cur_dict

    for item in elems.data:
          cid = item.id
          name = item.name
          pid = item.compartment_id
          elem_with_children.setdefault(pid, []).append([cid,name])

    res = _build_children_sub_tree(conf.tenancy,'tenancy')
    return res


def resource_list(conf:OCIConfig):
    """
    recursively visit all  compartments in all regions and retrieve resources
    """
    def _retrieve_resources_in_compartment(tree, region, traverse_level=0):
        
        logging.info('{} {}'.format('__'*traverse_level, tree['name']))
        if 'nested' in tree:
            for nested_item in tree['nested']:
                traverse_level += 1
                _retrieve_resources_in_compartment(nested_item, region, traverse_level)
                traverse_level -= 1
        _get_instance_resources(compute_client, tree, region)
        _get_network_resources(network_client, tree, region)
        _get_bv_resorces(bv_client,tree,region)

    for r in conf._compartments_tree.keys():
        #logging.info(r)
        conf.workon_region = r
        logging.info("visit compartments in {} region".format(r))

        compute_client = oci.core.ComputeClient(conf.config)
        compute_client.get_instance()
        network_client = oci.core.VirtualNetworkClient(conf.config)
        bv_client = oci.core.BlockstorageClient(conf.config)

        #bv_client.list_volumes('').data
        
        _retrieve_resources_in_compartment(conf._compartments_tree[r],r)


def _get_instance_resources(compute_client,tree,region):
    """
    retrieve instances and vnics
    """
    ilist = oci.pagination.list_call_get_all_results(compute_client.list_instances,compartment_id=tree['id'])

    def _get_nested_resources(api_list_call, res: OciResource):
        try:
            rlist = oci.pagination.list_call_get_all_results(api_list_call,compartment_id=tree['id'], instance_id=i.id)
            for r in rlist.data:
                instance[res.resource_type] = res(r)
        except:
            logging.error('unable to retrieve {} in [{}] Instance {}'.format(res.resource_type, region, i.id))

    for i in ilist.data:
        instance = OciInstance(i)

        _get_nested_resources(compute_client.list_vnic_attachments, OciVnic)

        tree.setdefault(instance.resource_type, []).append(instance)


def _get_network_resources(network_client,tree,region):
    """
    retrieve: vcn, subnet, gateways, secury list, route tables
    """
    ilist = oci.pagination.list_call_get_all_results(network_client.list_vcns,compartment_id=tree['id'])

    def _get_nested_resources(api_list_call, res: OciResource):
        try:
            rlist = oci.pagination.list_call_get_all_results(api_list_call,compartment_id=tree['id'], vcn_id=vcn.id)
            for r in rlist.data:
                vcn[res.resource_type] = res(r)
        except:
            logging.error('unable to retrieve {} in [{}] VCN {}'.format(res.resource_type, region, vcn.id))

    for i in ilist.data:
        vcn = OciVcn(i)

        _get_nested_resources(network_client.list_subnets, OciSubnet)
        _get_nested_resources(network_client.list_internet_gateways, OciInternetGw)
        _get_nested_resources(network_client.list_nat_gateways, OciNatGw)
        _get_nested_resources(network_client.list_security_lists, OciSecurityList)
        _get_nested_resources(network_client.list_route_tables, OciRouteTable)
        _get_nested_resources(network_client.list_local_peering_gateways, OciLocalPeeringGw)
        _get_nested_resources(network_client.list_service_gateways, OciServiceGw)

        tree.setdefault(vcn.resource_type, []).append(vcn)


def _get_bv_resorces(bv_client,tree,region):
    """
    retrieve block volumes
    """
    ilist = oci.pagination.list_call_get_all_results(bv_client.list_volumes,compartment_id=tree['id'])

    def _get_nested_resources(api_list_call, res: OciResource):
        try:
            rlist = oci.pagination.list_call_get_all_results(api_list_call,compartment_id=tree['id'], vcn_id=i.id)
            for r in rlist.data:
                bv[res.resource_type] = res(r)
        except:
            logging.error('unable to retrieve {} in [{}] Instance {}'.format(res.resource_type, region, i.id))

    for i in ilist.data:
        bv = OciBlockVolume(i)

        #_get_nested_resources(bv_client..., ...)

        tree.setdefault(bv.resource_type, []).append(bv)

