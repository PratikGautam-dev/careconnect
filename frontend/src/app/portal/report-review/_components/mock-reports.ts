export type ReportPriority = "Normal" | "High" | "Urgent";
export type ReportStatus = "Pending" | "Approved" | "Rejected";

export type MockReport = {
  id: number;
  reportId: string;
  patientName: string;
  age: number;
  gender: "Male" | "Female";
  reportType: string;
  uploadedBy: string;
  uploadedByRole: string;
  uploadDate: string;
  priority: ReportPriority;
  reviewingDoctor: string;
  reviewingDoctorSpecialty: string;
  status: ReportStatus;
  remarks: string | null;
};

/** Frontend-only mock data for /portal/report-review -- there's no backend
 * for report review yet (no reports table, no upload/review routes), per
 * the user's own "no backend, only frontend" instruction. This is a static
 * seed list the page mutates locally (approve/return/delete/flag), not a
 * fetched resource -- refreshing the page resets it. */
export const INITIAL_MOCK_REPORTS: MockReport[] = [
  { id: 1, reportId: "REP20260909001", patientName: "Rahul Kapoor", age: 32, gender: "Male", reportType: "Blood Test (CBC)", uploadedBy: "Priya Nair", uploadedByRole: "Nurse", uploadDate: "09 Sep 2026, 10:24 AM", priority: "Normal", reviewingDoctor: "Dr. Ananya Sharma", reviewingDoctorSpecialty: "Pathologist", status: "Pending", remarks: null },
  { id: 2, reportId: "REP20260909002", patientName: "Sneha Patel", age: 28, gender: "Female", reportType: "X-Ray Chest", uploadedBy: "Amit Kumar", uploadedByRole: "Lab Technician", uploadDate: "09 Sep 2026, 09:15 AM", priority: "High", reviewingDoctor: "Dr. Vikram Singh", reviewingDoctorSpecialty: "Radiologist", status: "Pending", remarks: null },
  { id: 3, reportId: "REP20260908003", patientName: "Aman Mehta", age: 45, gender: "Male", reportType: "MRI Brain", uploadedBy: "Neha Reddy", uploadedByRole: "Staff", uploadDate: "08 Sep 2026, 06:40 PM", priority: "Urgent", reviewingDoctor: "Dr. Rohan Mehta", reviewingDoctorSpecialty: "Radiologist", status: "Pending", remarks: null },
  { id: 4, reportId: "REP20260908004", patientName: "Pooja Gupta", age: 34, gender: "Female", reportType: "Thyroid Profile", uploadedBy: "Karan Shah", uploadedByRole: "Lab Technician", uploadDate: "08 Sep 2026, 02:18 PM", priority: "Normal", reviewingDoctor: "Dr. Neha Reddy", reviewingDoctorSpecialty: "Pathologist", status: "Approved", remarks: "Within normal range." },
  { id: 5, reportId: "REP20260908005", patientName: "Vikram Joshi", age: 52, gender: "Male", reportType: "Ultrasound Abdomen", uploadedBy: "Ritu Verma", uploadedByRole: "Nurse", uploadDate: "08 Sep 2026, 11:05 AM", priority: "High", reviewingDoctor: "Dr. Arjun Nair", reviewingDoctorSpecialty: "Radiologist", status: "Pending", remarks: null },
  { id: 6, reportId: "REP20260907006", patientName: "Meera Iyer", age: 29, gender: "Female", reportType: "HbA1c", uploadedBy: "Suresh Patel", uploadedByRole: "Lab Technician", uploadDate: "07 Sep 2026, 04:22 PM", priority: "Normal", reviewingDoctor: "Dr. Kavita Rao", reviewingDoctorSpecialty: "Pathologist", status: "Approved", remarks: "Slightly elevated, follow-up advised." },
  { id: 7, reportId: "REP20260907007", patientName: "Arjun Desai", age: 61, gender: "Male", reportType: "CT Scan Chest", uploadedBy: "Priya Nair", uploadedByRole: "Nurse", uploadDate: "07 Sep 2026, 01:17 PM", priority: "Urgent", reviewingDoctor: "Dr. Sameer Khan", reviewingDoctorSpecialty: "Radiologist", status: "Pending", remarks: null },
  { id: 8, reportId: "REP20260906008", patientName: "Kavya Nair", age: 38, gender: "Female", reportType: "Lipid Profile", uploadedBy: "Amit Kumar", uploadedByRole: "Lab Technician", uploadDate: "06 Sep 2026, 03:50 PM", priority: "Normal", reviewingDoctor: "Dr. Neha Reddy", reviewingDoctorSpecialty: "Pathologist", status: "Rejected", remarks: "Sample hemolyzed, re-test requested." },
  { id: 9, reportId: "REP20260906009", patientName: "Rohan Bhat", age: 40, gender: "Male", reportType: "Vitamin D", uploadedBy: "Ananya Verma", uploadedByRole: "Staff", uploadDate: "06 Sep 2026, 10:33 AM", priority: "Normal", reviewingDoctor: "Dr. Ananya Sharma", reviewingDoctorSpecialty: "Pathologist", status: "Approved", remarks: "Deficient, supplementation advised." },
  { id: 10, reportId: "REP20260905010", patientName: "Sana Khan", age: 27, gender: "Female", reportType: "Urine Routine", uploadedBy: "Ritu Verma", uploadedByRole: "Nurse", uploadDate: "05 Sep 2026, 05:12 PM", priority: "High", reviewingDoctor: "Dr. Kavita Rao", reviewingDoctorSpecialty: "Pathologist", status: "Pending", remarks: null },
  { id: 11, reportId: "REP20260905011", patientName: "Dev Malhotra", age: 55, gender: "Male", reportType: "ECG", uploadedBy: "Karan Shah", uploadedByRole: "Lab Technician", uploadDate: "05 Sep 2026, 02:05 PM", priority: "Urgent", reviewingDoctor: "Dr. Rohan Mehta", reviewingDoctorSpecialty: "Cardiologist", status: "Pending", remarks: null },
  { id: 12, reportId: "REP20260904012", patientName: "Ira Bose", age: 24, gender: "Female", reportType: "Pregnancy Panel", uploadedBy: "Priya Nair", uploadedByRole: "Nurse", uploadDate: "04 Sep 2026, 11:40 AM", priority: "Normal", reviewingDoctor: "Dr. Ananya Sharma", reviewingDoctorSpecialty: "Pathologist", status: "Approved", remarks: "All parameters normal." },
  { id: 13, reportId: "REP20260904013", patientName: "Farhan Ali", age: 48, gender: "Male", reportType: "Liver Function Test", uploadedBy: "Amit Kumar", uploadedByRole: "Lab Technician", uploadDate: "04 Sep 2026, 09:02 AM", priority: "High", reviewingDoctor: "Dr. Neha Reddy", reviewingDoctorSpecialty: "Pathologist", status: "Rejected", remarks: "Incomplete panel, resubmission needed." },
  { id: 14, reportId: "REP20260903014", patientName: "Nisha Verma", age: 31, gender: "Female", reportType: "X-Ray Knee", uploadedBy: "Neha Reddy", uploadedByRole: "Staff", uploadDate: "03 Sep 2026, 06:15 PM", priority: "Normal", reviewingDoctor: "Dr. Vikram Singh", reviewingDoctorSpecialty: "Radiologist", status: "Approved", remarks: "No fracture seen." },
  { id: 15, reportId: "REP20260903015", patientName: "Yash Raut", age: 19, gender: "Male", reportType: "Kidney Function Test", uploadedBy: "Suresh Patel", uploadedByRole: "Lab Technician", uploadDate: "03 Sep 2026, 03:30 PM", priority: "Normal", reviewingDoctor: "Dr. Kavita Rao", reviewingDoctorSpecialty: "Pathologist", status: "Pending", remarks: null },
];

export function initialStats() {
  return {
    pendingReviews: { value: 24, deltaPct: 20 },
    approvedReports: { value: 186, deltaPct: 15 },
    rejectedReports: { value: 16, deltaPct: 8 },
    urgentReports: { value: 7, deltaPct: 75 },
  };
}

export const REPORTS_BY_TYPE_THIS_MONTH = [
  { type: "Blood Test", count: 98 },
  { type: "X-Ray", count: 76 },
  { type: "MRI/CT", count: 52 },
  { type: "Ultrasound", count: 34 },
  { type: "Urine Test", count: 28 },
  { type: "Others", count: 41 },
];

export type ActivityItem = {
  id: number;
  time: string;
  title: string;
  subtitle: string;
  status: ReportStatus;
};

export const RECENT_REPORT_ACTIVITY: ActivityItem[] = [
  { id: 1, time: "10:24 AM", title: "Report uploaded - Blood Test (CBC)", subtitle: "Rahul Kapoor • Uploaded by Priya Nair", status: "Pending" },
  { id: 2, time: "09:15 AM", title: "Report uploaded - X-Ray Chest", subtitle: "Sneha Patel • Uploaded by Amit Kumar", status: "Pending" },
  { id: 3, time: "06:40 PM", title: "Urgent report uploaded - MRI Brain", subtitle: "Aman Mehta • Uploaded by Neha Reddy", status: "Pending" },
  { id: 4, time: "04:22 PM", title: "Report approved - HbA1c", subtitle: "Meera Iyer • Approved by Dr. Kavita Rao", status: "Approved" },
];
