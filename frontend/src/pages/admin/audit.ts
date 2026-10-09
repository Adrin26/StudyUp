const ACTION_LABELS: Record<string, string> = {
  "user.create": "Account created",
  "user.role_change": "Role changed",
  "auth.password_reset_requested": "Password reset requested",
  "auth.password_reset_completed": "Password reset completed",
  "auth.password_changed": "Password changed",
  "user.update": "Account updated",
  "user.disable": "Account disabled",
  "user.reactivate": "Account reactivated",
  "user.invitation_sent": "Invitation sent",
  "user.subjects_update": "Student subjects changed",
  "user.import": "Users imported from CSV",
  "enrolment.enrol": "Student enrolled",
  "enrolment.transfer": "Student transferred",
  "enrolment.withdraw": "Student withdrawn from class",
  "class.create": "Class created",
  "class.update": "Class updated",
  "class.archive": "Class archived",
  "class.restore": "Class restored",
  "teacher_assignment.create": "Teacher assigned",
  "teacher_assignment.delete": "Teacher assignment removed",
  "school.update": "School profile updated",
  "academic_year.create": "Academic year created",
  "academic_year.update": "Academic year updated",
  "academic_year.set_current": "Current academic year changed",
  "academic_term.create": "Term added",
  "academic_term.update": "Term updated",
  "academic_term.delete": "Term deleted",
};

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/[._]/g, " ");
}

export function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
