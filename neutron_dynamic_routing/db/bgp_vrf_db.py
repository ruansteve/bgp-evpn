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

from neutron.db import common_db_mixin
from neutron.db import model_base
from neutron.db import models_v2

from oslo_db import exception as db_exc
from oslo_log import log
from oslo_utils import uuidutils

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import exc

from neutron_dynamic_routing._i18n import _LI, _LW
from neutron_dynamic_routing.extensions import vrf as vrf_ext
from neutron_dynamic_routing.services.bgp.common import utils

LOG = log.getLogger(__name__)


class BgpSpeakerVrfBinding(model_base.BASEV2, models_v2.HasId,
                           models_v2.HasTenant):

    """Represents a mapping between BGP speaker and VRF"""

    __tablename__ = 'bgp_speaker_vrf_bindings'

    speaker_id = sa.Column(sa.String(length=36),
                               sa.ForeignKey('bgp_speakers.id'),
                               nullable=False)
    vrf_id = sa.Column(sa.String(length=36),
                       sa.ForeignKey('vrfs.id'),
                       nullable=False)
    sa.UniqueConstraint(speaker_id, vrf_id)


class BGPVRFRouterAssociation(model_base.BASEV2, models_v2.HasId,
                              models_v2.HasTenant):
    """Represents the association between a vrf and a router."""
    __tablename__ = 'vrf_router_bindings'

    vrf_id = sa.Column(sa.String(36),
                       sa.ForeignKey('vrfs.id'),
                       nullable=False)
    router_id = sa.Column(sa.String(36),
                          sa.ForeignKey('routers.id'),
                          nullable=False)
    sa.UniqueConstraint(vrf_id, router_id)


class BGPVRF(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents a BGPVRF Object."""
    __tablename__ = 'vrfs'

    name = sa.Column(sa.String(255), nullable=True)
    type = sa.Column(sa.Enum("evpn", name="vrf_type"),
                     nullable=True)
    import_targets = sa.Column(sa.String(255), nullable=True)
    export_targets = sa.Column(sa.String(255), nullable=True)
    route_distinguishers = sa.Column(sa.String(255), nullable=True)
    segmentation_id = sa.Column(sa.BigInteger(), nullable=True)

    router_associations = orm.relationship("BGPVRFRouterAssociation",
                                           backref="vrf_router_bindings",
                                           lazy='joined',
                                           cascade='all, delete-orphan')


class BGPVRFPluginDb(common_db_mixin.CommonDbMixin):
    """BGPVRF service plugin database class using SQLAlchemy models."""

    def _get_vrfs_for_tenant(self, session, tenant_id, fields):
        try:
            qry = session.query(BGPVRF)
            vrfs = qry.filter_by(tenant_id=tenant_id)
        except exc.NoResultFound:
            return

        return [self._make_vrf_dict(vrf, fields=fields)
                for vrf in vrfs]

    def _make_vrf_dict(self, vrf_db, fields=None):
        router_list = [router_assocs.router_id for router_assocs in
                       vrf_db.router_associations]
        res = {
            'id': vrf_db['id'],
            'tenant_id': vrf_db['tenant_id'],
            'routers': router_list,
            'name': vrf_db['name'],
            'type': vrf_db['type'],
            'route_distinguishers':
                utils.rtrd_str2list(vrf_db['route_distinguishers']),
            'import_targets':
                utils.rtrd_str2list(vrf_db['import_targets']),
            'export_targets':
                utils.rtrd_str2list(vrf_db['export_targets']),
            'segmentation_id': str(vrf_db['segmentation_id'])
        }
        return self._fields(res, fields)

    def create_vrf(self, context, vrf):
        LOG.debug("vrf: %s", vrf)
        vrf_info = vrf['vrf']
        i_rt = utils.rtrd_list2str(vrf_info['import_targets'])
        e_rt = utils.rtrd_list2str(vrf_info['export_targets'])
        rd = utils.rtrd_list2str(vrf_info.get('route_distinguishers', ''))

        with context.session.begin(subtransactions=True):
            vrf_db = BGPVRF(
                id=uuidutils.generate_uuid(),
                tenant_id=vrf_info['tenant_id'],
                name=vrf_info['name'],
                type=vrf_info['type'],
                import_targets=i_rt,
                export_targets=e_rt,
                route_distinguishers=rd,
                segmentation_id=long(vrf_info['segmentation_id'])
            )
            context.session.add(vrf_db)

        return self._make_vrf_dict(vrf_db)

    def get_vrfs(self, context, filters=None, fields=None):
        return self._get_collection(context, BGPVRF, self._make_vrf_dict,
                                    filters=filters, fields=fields)

    def _get_vrf(self, context, id):
        try:
            return self._get_by_id(context, BGPVRF, id)
        except exc.NoResultFound:
            raise vrf_ext.BGPVRFNotFound(id=id)

    def get_vrf(self, context, id, fields=None):
        vrf_db = self._get_vrf(context, id)
        return self._make_vrf_dict(vrf_db, fields)

    def update_vrf(self, context, id, vrf):
        LOG.debug("vrf: %s", vrf)
        vrf_info = vrf['vrf']
        fields = None
        with context.session.begin(subtransactions=True):
            vrf_db = self._get_vrf(context, id)
            if vrf_info:
                # Format Route Target lists to string
                if 'import_targets' in vrf_info:
                    i_rt = utils.rtrd_list2str(vrf_info['import_targets'])
                    vrf_info['import_targets'] = i_rt
                if 'export_targets' in vrf_info:
                    e_rt = utils.rtrd_list2str(vrf_info['export_targets'])
                    vrf_info['export_targets'] = e_rt
                if 'route_distinguishers' in vrf_info:
                    rd = utils.rtrd_list2str(vrf_info['route_distinguishers'])
                    vrf_info['route_distinguishers'] = rd

                vrf_db.update(vrf_info)
        return self._make_vrf_dict(vrf_db, fields)

    def delete_vrf(self, context, id):
        LOG.debug("vrf id: %s", id)
        with context.session.begin(subtransactions=True):
            vrf_db = self._get_vrf(context, id)
            vrf = self._make_vrf_dict(vrf_db)
            context.session.delete(vrf_db)
        return vrf

    def find_vrfs_for_router(self, context, router_id):
        try:
            query = (context.session.query(BGPVRF).
                     join(BGPVRFRouterAssociation).
                     filter(BGPVRFRouterAssociation.router_id == router_id))
        except exc.NoResultFound:
            return

        return [self._make_vrf_dict(vrf)
                for vrf in query.all()]

    def _make_router_assoc_dict(self, router_assoc_db, fields=None):
        res = {'id': router_assoc_db['id'],
               'vrf_id': router_assoc_db['vrf_id'],
               'router_id': router_assoc_db['router_id']}
        return self._fields(res, fields)

    def _get_router_assoc(self, context, vrf_id, router_id):
        try:
            query = self._model_query(context, BGPVRFRouterAssociation)
            return query.filter(BGPVRFRouterAssociation.vrf_id == vrf_id,
                                BGPVRFRouterAssociation.router_id == router_id,
                                ).one()
        except exc.NoResultFound:
            raise vrf_ext.BGPVRFRouterAssocNotFound(vrf_id=vrf_id,
                                                    router_id=router_id)

    def add_vrf_router_assoc(self, context, vrf_id, router_association):
        LOG.debug("vrf id %s, association %s", vrf_id, router_association)
        router_id = router_association['router_id']
        try:
            with context.session.begin(subtransactions=True):
                router_assoc_db = BGPVRFRouterAssociation(
                    id=uuidutils.generate_uuid(),
                    vrf_id=vrf_id,
                    router_id=router_id)
                context.session.add(router_assoc_db)
            return self._make_router_assoc_dict(router_assoc_db)
        except db_exc.DBDuplicateEntry:
            LOG.warning(_LW("router %(router_id)s is already associated to "
                            "BGPVRF %(vrf_id)s"),
                        {'router_id': router_id,
                         'vrf_id': vrf_id})
            raise vrf_ext.BGPVRFRouterAssocAlreadyExists(
                vrf_id=vrf_id, router_id=router_id)

    def remove_vrf_router_assoc(self, context, vrf_id, router_association):
        LOG.debug("association %s", router_association)
        router_id = router_association['router_id']
        LOG.info(_LI("deleting vrf %(vrf_id)s router %(router_id)s "
                     "association"),
                 {'vrf_id': vrf_id, 'router_id': router_id})
        with context.session.begin():
            router_assoc_db = self._get_router_assoc(context,
                                                     vrf_id, router_id)
            router_assoc = self._make_router_assoc_dict(router_assoc_db)
            context.session.delete(router_assoc_db)
        return router_assoc

    def _make_speaker_assoc_dict(self, speaker_assoc_db, fields=None):
        res = {'id': speaker_assoc_db['id'],
               'vrf_id': speaker_assoc_db['vrf_id'],
               'speaker_id': speaker_assoc_db['speaker_id']}
        return self._fields(res, fields)

    def _get_speaker_assoc(self, context, vrf_id, speaker_id):
        try:
            query = self._model_query(context, BgpSpeakerVrfBinding)
            return query.filter(BgpSpeakerVrfBinding.vrf_id == vrf_id,
                                BgpSpeakerVrfBinding.speaker_id == speaker_id,
                                ).one()
        except exc.NoResultFound:
            raise vrf_ext.BGPVRFSpeakerAssocNotFound(vrf_id=vrf_id,
                                                    speaker_id=speaker_id)

    def add_vrf_speaker_assoc(self, context, vrf_id, speaker_association):
        speaker_id = speaker_association['speaker_id']
        LOG.info(_LI("Add speaker association %(speaker_id)s "
                     "for BGPVRF %(vrf_id)s"),
                 {'speaker_id': speaker_id, 'vrf_id': vrf_id})
        try:
            with context.session.begin(subtransactions=True):
                speaker_assoc_db = BgpSpeakerVrfBinding(
                    id=uuidutils.generate_uuid(),
                    vrf_id=vrf_id,
                    speaker_id=speaker_id)
                context.session.add(speaker_assoc_db)
            return self._make_speaker_assoc_dict(speaker_assoc_db)
        except db_exc.DBDuplicateEntry:
            LOG.warning(_LW("Speaker %(speaker_id)s is already associated to "
                            "BGPVRF %(vrf_id)s"),
                        {'speaker_id': speaker_id,
                         'vrf_id': vrf_id})
            raise vrf_ext.BGPVRFSpeakerAssocAlreadyExists(
                vrf_id=vrf_id, speaker_id=speaker_id)

    def remove_vrf_speaker_assoc(self, context, vrf_id, speaker_association):
        speaker_id = speaker_association['speaker_id']
        LOG.info(_LI("deleting speaker association %(speaker_id)s "
                     "for BGPVRF %(vrf_id)s"),
                 {'speaker_id': speaker_id, 'vrf_id': vrf_id})
        with context.session.begin():
            speaker_assoc_db = self._get_speaker_assoc(context,
                                                     vrf_id, speaker_id)
            speaker_assoc = self._make_speaker_assoc_dict(speaker_assoc_db)
            context.session.delete(speaker_assoc_db)
        return speaker_assoc

    def get_vrf_speaker_assoc(self, context, assoc_id, vrf_id,
                              fields=None):
        pass
