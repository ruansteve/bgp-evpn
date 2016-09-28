#    Copyright 2016 Huawei Technologies India Pvt Limited.
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
#

"""add vrf tables

Revision ID: b7a91e8ba52c
Revises: f399fa0f5f25
Create Date: 2016-09-17 06:25:30.821842

"""

# revision identifiers, used by Alembic.
revision = 'b7a91e8ba52c'
down_revision = 'f399fa0f5f25'

from alembic import op
import sqlalchemy as sa

vrf_type = sa.Enum("evpn", name="vpn_types")


def upgrade():

    op.create_table(
        'vrfs',
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=255), nullable=True),
        sa.Column('type', vrf_type, nullable=False),
        sa.Column('import_targets', sa.String(255), nullable=True),
        sa.Column('export_targets', sa.String(255), nullable=True),
        sa.Column('route_distinguishers', sa.String(255), nullable=True),
        sa.Column('segmentation_id', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'vrf_router_bindings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=255), nullable=True),
        sa.Column('vrf_id', sa.String(length=36),
                  sa.ForeignKey('vrfs.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('router_id', sa.String(length=36),
                  sa.ForeignKey('routers.id', ondelete='CASCADE'),
                  nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(vrf_id, router_id)
    )

    op.create_table(
        'bgp_speaker_vrf_bindings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=255), nullable=True),
        sa.Column('vrf_id', sa.String(length=36),
                  sa.ForeignKey('vrfs.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('speaker_id', sa.String(length=36),
                  sa.ForeignKey('bgp_speakers.id', ondelete='CASCADE'),
                  nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(vrf_id, speaker_id)
    )
