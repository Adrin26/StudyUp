import { Suspense, lazy, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/app-shell";
import { PageLoader } from "@/components/states";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/types";
import LoginPage from "@/pages/Login";
import StudentDashboard from "@/pages/student/Dashboard";
import SubjectPage from "@/pages/student/Subject";
import TopicPage from "@/pages/student/Topic";
import LessonPage from "@/pages/student/Lesson";
import QuizPage from "@/pages/student/Quiz";
import ResultsPage from "@/pages/student/Results";
import PracticePage from "@/pages/student/Practice";
import PracticeSessionPage from "@/pages/student/PracticeSession";
import CommunityPage from "@/pages/community/Community";
import PostPage from "@/pages/community/Post";
const TeacherDashboard = lazy(() => import("@/pages/teacher/Dashboard"));
const TeacherStudentPage = lazy(() => import("@/pages/teacher/StudentDetail"));
const ExamsPage = lazy(() => import("@/pages/teacher/Exams"));
const ExamGeneratorPage = lazy(() => import("@/pages/teacher/ExamGenerator"));
const ExamDetailPage = lazy(() => import("@/pages/teacher/ExamDetail"));

function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8"><PageLoader /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={user.role === "student" ? "/" : "/teacher"} replace />;
  return <>{children}</>;
}

export default function App() {
  const { user, loading } = useAuth();
  return (
    <Suspense fallback={<div className="p-8"><PageLoader /></div>}>
    <Routes>
      <Route path="/login" element={!loading && user ? <Navigate to={user.role === "student" ? "/" : "/teacher"} replace /> : <LoginPage />} />

      <Route element={<RequireRole roles={["student"]}><AppShell /></RequireRole>}>
        <Route index element={<StudentDashboard />} />
        <Route path="subjects/:subjectId" element={<SubjectPage />} />
        <Route path="topics/:topicId" element={<TopicPage />} />
        <Route path="practice" element={<PracticePage />} />
        <Route path="practice/set/:setId" element={<PracticeSessionPage />} />
        <Route path="community" element={<CommunityPage space="student" />} />
        <Route path="community/:postId" element={<PostPage />} />
      </Route>

      <Route path="topics/:topicId/learn" element={<RequireRole roles={["student"]}><LessonPage /></RequireRole>} />
      <Route path="quiz/:setId" element={<RequireRole roles={["student"]}><QuizPage /></RequireRole>} />
      <Route path="quiz/:setId/results" element={<RequireRole roles={["student"]}><AppShellFree><ResultsPage /></AppShellFree></RequireRole>} />

      <Route path="teacher" element={<RequireRole roles={["teacher", "admin"]}><AppShell /></RequireRole>}>
        <Route index element={<TeacherDashboard />} />
        <Route path="students/:studentId" element={<TeacherStudentPage />} />
        <Route path="exams" element={<ExamsPage />} />
        <Route path="exams/new" element={<ExamGeneratorPage />} />
        <Route path="exams/:examId" element={<ExamDetailPage />} />
        <Route path="community" element={<CommunityPage space="teacher" />} />
        <Route path="student-community" element={<CommunityPage space="student" />} />
        <Route path="community/:postId" element={<PostPage />} />
        <Route path="student-community/:postId" element={<PostPage />} />
      </Route>

      <Route path="*" element={<Navigate to={user ? (user.role === "student" ? "/" : "/teacher") : "/login"} replace />} />
    </Routes>
    </Suspense>
  );
}

function AppShellFree({ children }: { children: ReactNode }) {
  return <div className="mx-auto min-h-dvh max-w-3xl px-4 py-6 sm:py-10">{children}</div>;
}
