from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class FileProcessStageSummary(BaseModel):
    processTypeId: int
    processTypeName: str
    sortOrder: int
    statusId: int
    statusName: str
    assignedToUserId: int | None
    activeAssignmentId: int | None
    lastFailureReason: str | None


class FileOut(BaseModel):
    FileID: int
    FileName: str
    PhaseID: int
    CategoryID: int | None
    SubCategoryID: int | None
    StatusID: int
    AssignedToUserID: int | None
    CurrentVersionID: int | None
    ActiveAssignmentID: int | None = None
    UpdatedAt: datetime
    IsActive: bool = True
    Priority: str = "Normal"
    processStages: list[FileProcessStageSummary] = []
    myActiveAssignmentId: int | None = None

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    UserID: int
    Username: str
    roleNames: list[str]
    roleIds: list[int]
    PhaseID: int | None
    IsActive: bool
    enabledProcessTypeIds: list[int] = []
    pendingCount: int = 0
    isAvailable: bool = True
    isOnLeaveToday: bool = False


class MeOut(BaseModel):
    roleNames: list[str]


class LookupItem(BaseModel):
    id: int
    name: str


class CategoryLookupItem(BaseModel):
    id: int
    phaseId: int
    name: str


class SubCategoryLookupItem(BaseModel):
    id: int
    categoryId: int
    name: str


class LookupsOut(BaseModel):
    phases: list[LookupItem]
    statuses: list[LookupItem]
    categories: list[CategoryLookupItem]
    subCategories: list[SubCategoryLookupItem]
    roles: list[LookupItem]
    processTypes: list[LookupItem]


class CreatePhaseRequest(BaseModel):
    name: str


class CreateCategoryRequest(BaseModel):
    phase_id: int
    name: str


class CreateSubCategoryRequest(BaseModel):
    category_id: int
    name: str


class UpdateTaxonomyNodeRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class PhaseAdminOut(BaseModel):
    id: int
    name: str
    isActive: bool
    fileCount: int
    userCount: int


class CategoryAdminOut(BaseModel):
    id: int
    phaseId: int
    phaseName: str
    name: str
    isActive: bool
    fileCount: int


class SubCategoryAdminOut(BaseModel):
    id: int
    categoryId: int
    categoryName: str
    phaseId: int
    phaseName: str
    name: str
    isActive: bool
    fileCount: int


class TaxonomyAdminOut(BaseModel):
    phases: list[PhaseAdminOut]
    categories: list[CategoryAdminOut]
    subCategories: list[SubCategoryAdminOut]


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role_ids: list[int] = Field(min_length=1)
    phase_id: int | None = None


class UpdateUserRequest(BaseModel):
    role_ids: list[int] = Field(min_length=1)
    phase_id: int | None = None
    is_active: bool
    is_available: bool = True


class ResetPasswordRequest(BaseModel):
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class DashboardFilterParams(BaseModel):
    phase_id: int | None = None
    category_id: int | None = None
    sub_category_id: int | None = None
    status_id: int | None = None
    assigned_to_user_id: int | None = None  # honored only for Admin callers
    process_type_id: int | None = None  # when set, status_id/assigned_to_user_id filter that stage
    is_active: bool | None = None  # unset shows both active and inactive files
    search: str | None = None  # matches file name OR phase/category/sub-category name


class AuditTrailFilterParams(BaseModel):
    file_id: int | None = None
    user_id: int | None = None
    action: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class AuditTrailEntryOut(BaseModel):
    auditTrailId: int
    fileId: int
    fileName: str
    action: str
    performedByUserId: int
    performedByUsername: str
    oldValue: str | None
    newValue: str | None
    timestamp: datetime


class AuditTrailPageOut(BaseModel):
    items: list[AuditTrailEntryOut]
    total: int
    page: int
    pageSize: int


class CalendarDayCountOut(BaseModel):
    date: str
    assignedCount: int
    completedCount: int
    failedCount: int
    repairedCount: int


class CalendarMonthOut(BaseModel):
    year: int
    month: int
    days: list[CalendarDayCountOut]


class CalendarEventOut(BaseModel):
    fileId: int
    fileName: str
    processTypeId: int
    processTypeName: str
    assignedToUserId: int
    assignedToUsername: str
    event: str  # "Assigned" | "Completed" | "Failed" | "Repair" | "Updated"
    eventTs: datetime
    failureReason: str | None


class CalendarDayDetailOut(BaseModel):
    date: str
    events: list[CalendarEventOut]


class BucketCountOut(BaseModel):
    label: str
    date: str | None = None
    count: int


class WeekSeriesOut(BaseModel):
    days: list[BucketCountOut]


class MonthSeriesOut(BaseModel):
    days: list[BucketCountOut]


class YearSeriesOut(BaseModel):
    months: list[BucketCountOut]


class ReportsTotalsOut(BaseModel):
    today: int
    thisWeek: int
    thisMonth: int
    thisYear: int


class ReportsCompletionsOut(BaseModel):
    referenceDate: str
    totals: ReportsTotalsOut
    week: WeekSeriesOut
    month: MonthSeriesOut
    year: YearSeriesOut
    weekComparison: list[BucketCountOut]
    monthComparison: list[BucketCountOut]


class TaxonomyProgressItemOut(BaseModel):
    id: int
    name: str
    totalFiles: int
    completedFiles: int
    completionPct: float
    isFullyCompleted: bool


class TaxonomyProgressOut(BaseModel):
    phases: list[TaxonomyProgressItemOut]
    categories: list[TaxonomyProgressItemOut]
    subCategories: list[TaxonomyProgressItemOut]


class DuplicateResolution(str, Enum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    NEW_VERSION = "new_version"


class CsvImportRow(BaseModel):
    file_name: str
    phase_name: str
    category_name: str | None = None
    sub_category_name: str | None = None
    source_path: str


class CsvImportConflict(BaseModel):
    row: CsvImportRow
    existing_file_id: int | None = None  # None when the conflict is only against another row in this same batch
    existing_version_number: int = 0
    existing_phase_name: str | None = None
    existing_category_name: str | None = None
    existing_sub_category_name: str | None = None
    conflict_scope: str = "database"  # "database" (already in SQL, anywhere) | "batch" (duplicate within this import)


class CsvImportPreview(BaseModel):
    new_rows: list[CsvImportRow]
    conflicts: list[CsvImportConflict]


class CsvImportResolutionEntry(BaseModel):
    file_name: str
    phase_name: str
    resolution: DuplicateResolution


class CsvImportCommitRequest(BaseModel):
    rows: list[CsvImportRow]
    resolutions: list[CsvImportResolutionEntry] = []  # only needed for rows that conflicted


class MoveCategoryRequest(BaseModel):
    file_ids: list[int]
    category_id: int | None = None
    sub_category_id: int | None = None


class MovePhaseRequest(BaseModel):
    file_ids: list[int]
    phase_id: int


class ProcessTypeAdminOut(BaseModel):
    id: int
    name: str
    sortOrder: int
    isActive: bool
    workerCount: int


class CreateProcessTypeRequest(BaseModel):
    name: str


class ReorderProcessTypesRequest(BaseModel):
    ordered_ids: list[int]


class WorkerProcessPathIn(BaseModel):
    process_type_id: int
    pending_path: str
    complete_path: str
    is_active: bool = True


class WorkerProcessPathOut(BaseModel):
    processTypeId: int
    processTypeName: str
    pendingPath: str
    completePath: str
    isActive: bool


class AssignRequest(BaseModel):
    user_id: int
    process_type_id: int


class MarkFailedRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class RejectAssignmentRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    reassign_to_user_id: int | None = None  # None => reassign to the same worker who submitted


class ProcessAttemptOut(BaseModel):
    assignmentId: int
    processTypeId: int
    processTypeName: str
    assignedToUserId: int
    assignedToUsername: str
    statusId: int
    statusName: str
    assignedTs: datetime
    completionTs: datetime | None
    failureReason: str | None
    sourcePath: str | None
    destPath: str | None
    isActive: bool


class FileProcessStageOut(BaseModel):
    processTypeId: int
    processTypeName: str
    sortOrder: int
    statusId: int
    statusName: str
    assignedToUserId: int | None
    lastFailureReason: str | None
    attempts: list[ProcessAttemptOut]


class FileProcessHistoryOut(BaseModel):
    fileId: int
    fileName: str
    stages: list[FileProcessStageOut]


class SetActiveRequest(BaseModel):
    is_active: bool


class NotificationOut(BaseModel):
    id: int
    type: str
    message: str
    fileId: int | None
    isRead: bool
    createdAt: datetime


class NotificationsPageOut(BaseModel):
    items: list[NotificationOut]
    unreadCount: int


class PendingApprovalOut(BaseModel):
    fileId: int
    fileName: str
    processTypeId: int
    processTypeName: str
    submittedByUserId: int
    submittedByUsername: str
    submittedAt: datetime | None


class LowWorkloadWorkerOut(BaseModel):
    userId: int
    username: str
    pendingCount: int


class StaleAssignmentOut(BaseModel):
    assignmentId: int
    fileId: int
    fileName: str
    processTypeId: int
    processTypeName: str
    assignedToUserId: int
    assignedToUsername: str
    assignedTs: datetime
    ageDays: int


class AdminWorkboardOut(BaseModel):
    pendingApprovals: list[PendingApprovalOut]
    lowWorkloadWorkers: list[LowWorkloadWorkerOut]
    lowWorkloadThreshold: int
    checkedWorkerCount: int  # how many workers have an active WorkerProcessPath at all - distinguishes
    # "everyone's fine" (this is > 0, lowWorkloadWorkers is empty) from
    # "nobody's configured yet" (this is 0) - both look like an empty list otherwise.
    staleAssignments: list[StaleAssignmentOut] = []
    staleAssignmentDays: int = 3


class FilePriority(str, Enum):
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"
    URGENT = "Urgent"


class PriorityChangeRequest(BaseModel):
    priority: FilePriority


class AvailabilityRequest(BaseModel):
    is_available: bool


class AppSettingsOut(BaseModel):
    lowWorkloadThreshold: int
    staleAssignmentDays: int


class UpdateAppSettingsRequest(BaseModel):
    low_workload_threshold: int = Field(ge=1)
    stale_assignment_days: int = Field(ge=1)


class UserLeaveOut(BaseModel):
    id: int
    userId: int
    startDate: date
    endDate: date
    createdAt: datetime


class CreateLeaveRequest(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _check_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class MyProfileOut(BaseModel):
    userId: int
    username: str
    roleNames: list[str]
    phaseId: int | None
    isAvailable: bool
