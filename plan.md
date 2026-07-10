# Project Management Tool: Development Plan

## 1. Overview
- **Objective:** Semi-automated 3D file management (Polish -> GLB -> Render) with SMB folder movement.
- **Stack:** Python (FastAPI), Microsoft SQL Server, AG-Grid (Frontend).

## 2. Database Schema (SQL Server)
- **Users:** UserId, Username, PasswordHash, RoleId, IsActive.
- **Files:** FileID, File_Name, Version_ID, Status, AssignedTo_UserID, Parent_File_ID.
- **TaskAssignments:** AssignmentID, FileID, Assigned_TS, Completion_TS, Audit_Trail_ID.
- **Settings:** Role_Root_Paths (e.g., Z:\Polish_Folder\).

## 3. Workflow Logic (The "Safe-Transfer" Pipeline)
- **Import:** CSV -> Staging -> Duplicate Check -> Admin Choice (Skip/Overwrite/New Version).
- **Assignment:** Admin assigns task -> System checks for file locks -> Move folder (`Copy-Verify-Delete`).
- **Completion:** User clicks "Complete" -> Record `Completion_TS` -> Status updates -> Next phase becomes available.

## 4. Admin Command Center
- **Dashboard:** Grid with filters for Phase, Category, Sub-Category.
- **Corrections:** Admin reset button for accidental completions.
- **Reporting:** SQL Views for monthly/yearly reports -> Export to PDF/Excel.

## 5. Security & RBAC
- **Roles:** Admin, Polish Artist, GLB Artist, Render Artist.
- **Constraint:** Dropdowns in Assignment Grid restricted by User Role.