from decimal import Decimal

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.unit_of_work import UnitOfWork
from app.modules.milestones.application.use_cases import GetTotalMilestoneWeight
from app.modules.milestones.infrastructure.repositories import SqlAlchemyMilestoneRepository
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.presentation.dependencies import get_notifier
from app.modules.payments.application.use_cases import PaymentService
from app.modules.payments.presentation.dependencies import get_payment_repository
from app.modules.payments.domain.repositories import PaymentRepository
from app.modules.workflow.application.use_cases import (
    ApproveAgreement,
    CancelProject,
    GetAgreement,
    GetProjectWorkflow,
    ListMyProjects,
    RequestAgreementChanges,
    SelectFreelancer,
    StartWork,
    UpdateAgreement,
)
from app.modules.workflow.domain.repositories import MilestoneWeightReader, PaymentPort, WorkflowRepository
from app.modules.workflow.presentation.providers import get_actor, get_workflow_repository  # noqa: F401


class _MilestoneWeightAdapter:
    """Memakai kontrak get_total_weight milik modul milestones."""

    def __init__(self, session: Session):
        self._use_case = GetTotalMilestoneWeight(SqlAlchemyMilestoneRepository(session))

    def total_weight(self, project_id: str) -> Decimal:
        return self._use_case.execute(project_id)


def get_milestone_weight_reader(db: Session = Depends(get_db)) -> MilestoneWeightReader:
    return _MilestoneWeightAdapter(db)


def get_payment_port(payments: PaymentRepository = Depends(get_payment_repository)) -> PaymentPort:
    return PaymentService(payments)


def get_project_workflow_use_case(
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> GetProjectWorkflow:
    return GetProjectWorkflow(repository)


def get_agreement_use_case(repository: WorkflowRepository = Depends(get_workflow_repository)) -> GetAgreement:
    return GetAgreement(repository)


def select_freelancer_use_case(
    repository: WorkflowRepository = Depends(get_workflow_repository),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> SelectFreelancer:
    return SelectFreelancer(repository, notifier, uow)


def update_agreement_use_case(
    repository: WorkflowRepository = Depends(get_workflow_repository),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> UpdateAgreement:
    return UpdateAgreement(repository, notifier, uow)


def approve_agreement_use_case(
    repository: WorkflowRepository = Depends(get_workflow_repository),
    milestones: MilestoneWeightReader = Depends(get_milestone_weight_reader),
    payments: PaymentPort = Depends(get_payment_port),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> ApproveAgreement:
    return ApproveAgreement(repository, milestones, payments, notifier, uow)


def request_changes_use_case(
    repository: WorkflowRepository = Depends(get_workflow_repository),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> RequestAgreementChanges:
    return RequestAgreementChanges(repository, notifier, uow)


def cancel_project_use_case(
    repository: WorkflowRepository = Depends(get_workflow_repository),
    payments: PaymentPort = Depends(get_payment_port),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> CancelProject:
    return CancelProject(repository, payments, notifier, uow)


def start_work_use_case(
    repository: WorkflowRepository = Depends(get_workflow_repository),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> StartWork:
    return StartWork(repository, notifier, uow)


def list_my_projects_use_case(
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> ListMyProjects:
    return ListMyProjects(repository)
