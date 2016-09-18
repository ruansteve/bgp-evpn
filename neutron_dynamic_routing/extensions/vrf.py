# Copyright (c) 2016 IBM.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import resource_helper
from neutron.common import exceptions as n_exc

from oslo_log import log

from neutron_dynamic_routing._i18n import _
from neutron_dynamic_routing.extensions import bgp as bgp_ext

LOG = log.getLogger(__name__)


# Regular expression to validate Route Target list format
# ["<asn1>:<nn1>","<asn2>:<nn2>", ...] with asn and nn in range 0-65535
RT_REGEX = (r'^((?:0|[1-9]\d{0,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]'
            r'\d|6553[0-5]):(?:0|[1-9]\d{0,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d'
            r'{2}|655[0-2]\d|6553[0-5]))$')

BGPVRF_RESOURCE_NAME = 'vrf'
BGPVRF_BODY_KEY_NAME = 'vrf'
BGPVRF_TYPE_EVPN = 'evpn'
BGPVRF_EXT_ALIAS = 'vrf'


class BGPVRFNotFound(n_exc.NotFound):
    message = _("BGP VRF %(id)s could not be found")


class BGPVRFRouterAssocNotFound(n_exc.NotFound):
    message = _("BGP VRF %(vrf_id)s router %(router_id)s "
                "association could not be found ")


class BGPVRFRDNotSupported(n_exc.BadRequest):
    message = _("BGP VRF %(driver)s driver does not support to manually set "
                "route distinguisher")


class BGPVRFRouterAssociationNotSupported(n_exc.BadRequest):
    message = _("BGP VRF %(driver)s driver does not support router "
                "associations")


class BGPVRFRouterAssocAlreadyExists(n_exc.BadRequest):
    message = _("router %(router_id)s is already associated to "
                "BGP VRF %(vrf_id)s")


class BGPVRFMultipleRouterAssocNotSupported(n_exc.BadRequest):
    message = _("BGP VRF %(driver)s driver does not support multiple "
                "router association with a bgp vrf")


class BGPVRFDriverError(n_exc.NeutronException):
    message = _("%(method)s failed.")


def _validate_rt_list(data, valid_values=None):
    if data is None or data is "":
        return

    if not isinstance(data, list):
        msg = _("'%s' is not a list") % data
        LOG.debug(msg)
        return msg

    for item in data:
        msg = attr._validate_regex(item, RT_REGEX)
        if msg:
            LOG.debug(msg)
            return msg

    if len(set(data)) != len(data):
        msg = _("Duplicate items in the list: '%s'") % ', '.join(data)
        LOG.debug(msg)
        return msg

validators = {'type:route_target_list': _validate_rt_list}
attr.validators.update(validators)

RESOURCE_ATTRIBUTE_MAP = {
    BGPVRF_RESOURCE_NAME + 's': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True,
               'enforce_policy': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'required_by_policy': False,
                      'is_visible': True,
                      'enforce_policy': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'default': '',
                 'validate': {'type:string': None},
                 'is_visible': True,
                 'enforce_policy': True},
        'type': {'allow_post': True, 'allow_put': False,
                 'default': BGPVRF_TYPE_EVPN,
                 'validate': {'type:values': [BGPVRF_TYPE_EVPN]},
                 'is_visible': True,
                 'enforce_policy': True},
        'import_targets': {'allow_post': True, 'allow_put': True,
                           'default': [],
                           'convert_to': attr.convert_to_list,
                           'validate': {'type:route_target_list': None},
                           'is_visible': True,
                           'enforce_policy': True},
        'export_targets': {'allow_post': True, 'allow_put': True,
                           'default': [],
                           'convert_to': attr.convert_to_list,
                           'validate': {'type:route_target_list': None},
                           'is_visible': True,
                           'enforce_policy': True},
        'route_distinguishers': {'allow_post': True, 'allow_put': True,
                                 'default': [],
                                 'convert_to': attr.convert_to_list,
                                 'validate': {'type:route_target_list': None},
                                 'is_visible': True,
                                 'enforce_policy': True},
        'routers': {'allow_post': False, 'allow_put': False,
                    'is_visible': True,
                    'enforce_policy': True},
        'segmentation_id': {'allow_post': True, 'allow_put': True,
                            'is_visible': True,
                            'enforce_policy': True}
    },
}


class Vrf(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Neutron BGP Dynamic Routing Extension"

    @classmethod
    def get_alias(cls):
        return BGPVRF_EXT_ALIAS

    @classmethod
    def get_description(cls):
        return("BGP VRF")

    @classmethod
    def get_updated(cls):
        return "2016-05-10T15:37:00-00:00"

    @classmethod
    def get_resources(cls):
        plural_mappings = resource_helper.build_plural_mappings(
            {}, RESOURCE_ATTRIBUTE_MAP)
        plural_mappings['import_targets'] = 'import_target'
        plural_mappings['export_targets'] = 'export_target'
        plural_mappings['route_distinguishers'] = 'route_distinguishers'
        plural_mappings['router_associations'] = 'router_association'
        attr.PLURALS.update(plural_mappings)
        action_map = {BGPVRF_RESOURCE_NAME:
                      {'add_vrf_speaker_assoc': 'PUT',
                       'remove_vrf_speaker_assoc': 'PUT',
                       'add_vrf_router_assoc': 'PUT',
                       'remove_vrf_router_assoc': 'PUT'}}
        exts = resource_helper.build_resource_info(plural_mappings,
                                      RESOURCE_ATTRIBUTE_MAP,
                                      bgp_ext.BGP_EXT_ALIAS,
                                      action_map=action_map)

        return exts
