from typing import List, NamedTuple, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy_utils import UUIDType

from hetdesrun.models.code import NonEmptyValidStr, ValidStr
from hetdesrun.utils import State, Type

Base = declarative_base()


class FilterParams(BaseModel):
    # pylint: disable=too-many-instance-attributes
    type: Optional[Type] = Field(None, description="Filter for specified type")
    state: Optional[State] = Field(None, description="Filter for specified state")
    category: Optional[ValidStr] = Field(
        None, description="Filter for specified category"
    )
    revision_group_id: Optional[UUID] = Field(
        None, description="Filter for specified revision group id"
    )
    ids: Optional[List[UUID]] = Field(
        None, description="Filter for specified list of ids"
    )
    names: Optional[List[NonEmptyValidStr]] = Field(
        None, description="Filter for specified list of names"
    )
    include_deprecated: bool = Field(
        True,
        description=(
            "Set to True to additionally get those transformation revisions "
            "that the selected ones depend on"
        ),
    )
    include_dependencies: bool = Field(
        False,
        description=(
            "Set to False to omit transformation revisions with state DISABLED "
            "this will not affect included dependent transformation revisions"
        ),
    )
    unused: bool = Field(
        False,
        description=(
            "Set to True to obtain only those transformation revisions that are "
            "not contained in workflows that do not have the state DISABLED."
        ),
    )


class TransformationRevisionDBModel(Base):
    __tablename__ = "transformation_revisions"

    id: UUIDType = Column(UUIDType(binary=False), primary_key=True, default=uuid4)
    revision_group_id: UUIDType = Column(
        UUIDType(binary=False), default=uuid4, nullable=False
    )
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    category = Column(String, nullable=False)
    version_tag = Column(String, nullable=False)
    state = Column(Enum(State), nullable=False)
    type = Column(Enum(Type), nullable=False)
    documentation = Column(String, nullable=False)
    workflow_content = Column(
        JSON(none_as_null=True), nullable=True, default=lambda: None
    )
    component_code = Column(String, nullable=True)
    io_interface = Column(JSON, nullable=False)
    test_wiring = Column(JSON, nullable=False)
    released_timestamp = Column(DateTime, nullable=True)
    disabled_timestamp = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "revision_group_id",
            "version_tag",
            name="_revision_group_id_plus_version_tag_uc",
        ),
        CheckConstraint(
            """
            (
                (  (CASE WHEN component_code IS NULL THEN 0 ELSE 1 END)
                +  (CASE WHEN workflow_content IS NULL THEN 0 ELSE 1 END)
                ) = 1
            )
            """,
            name="_exactly_one_of_component_code_or_workflow_content_null_cc",
        ),
    )


class NestingDBModel(Base):
    __tablename__ = "nestings"

    workflow_id: UUIDType = Column(
        UUIDType(binary=False),
        ForeignKey(TransformationRevisionDBModel.id),
        primary_key=True,
        default=uuid4,
    )
    via_transformation_id: UUIDType = Column(
        UUIDType(binary=False),
        ForeignKey(TransformationRevisionDBModel.id),
        default=uuid4,
        nullable=False,
    )
    via_operator_id: UUIDType = Column(
        UUIDType(binary=False),
        primary_key=True,
        default=uuid4,
    )
    depth = Column(Integer, primary_key=True, nullable=False)
    nested_transformation_id: UUIDType = Column(
        UUIDType(binary=False),
        ForeignKey(TransformationRevisionDBModel.id),
        default=uuid4,
        nullable=False,
    )
    nested_operator_id: UUIDType = Column(
        UUIDType(binary=False),
        primary_key=True,
        default=uuid4,
    )

    workflow: TransformationRevisionDBModel = relationship(
        TransformationRevisionDBModel,
        foreign_keys=[workflow_id],
    )
    via_transformation: TransformationRevisionDBModel = relationship(
        TransformationRevisionDBModel, foreign_keys=[via_transformation_id]
    )
    nested_transformation: TransformationRevisionDBModel = relationship(
        TransformationRevisionDBModel, foreign_keys=[nested_transformation_id]
    )

    __table_args__ = (
        CheckConstraint(
            "depth > 0",
            name="_depth_natural_number_cc",
        ),
        CheckConstraint(
            """
            (
                (  (CASE WHEN depth > 1 THEN 1 ELSE 0 END)
                +( (CASE WHEN via_transformation_id = nested_transformation_id THEN 1 ELSE 0 END)
                  *(CASE WHEN via_operator_id = nested_operator_id THEN 1 ELSE 0 END)
                 )
                ) = 1
            )
            """,
            name="_via_ids_equal_nested_ids_for_direct_nesting_cc",
        ),
    )


class Descendant(NamedTuple):
    depth: int
    transformation_id: UUID
    operator_id: UUID
