export type HospitalOverview = {
  shortName: string;
  hospitalType: string;
  establishedYear: string;
  about: string;
};

export type RegistrationDetails = {
  registrationNumber: string;
  licenseNumber: string;
  issuingAuthority: string;
  licenseValidTill: string;
  registrationDate: string;
};

export type AccreditationDetails = {
  accreditationBody: string;
  accreditationNumber: string;
  validTill: string;
};

export type ContactInformation = {
  phone: string;
  alternatePhone: string;
  email: string;
  website: string;
  address: string;
};

export type EmergencyContact = {
  number: string;
  contactPerson: string;
  designation: string;
};

export type OperatingHours = {
  opdTimings: string;
  emergencyServices: string;
  pharmacyTimings: string;
  labServicesTimings: string;
};

export type BedCapacity = {
  totalBeds: number;
  icuBeds: number;
  generalBeds: number;
  semiPrivateBeds: number;
  privateRooms: number;
};

export type BranchType = "Main Campus" | "Branch";
export type BranchStatus = "Active" | "Inactive";

export type Branch = {
  id: number;
  name: string;
  location: string;
  type: BranchType;
  status: BranchStatus;
};

export type HospitalProfileState = {
  overview: HospitalOverview;
  logoDataUrl: string | null;
  coverDataUrl: string | null;
  registration: RegistrationDetails;
  accreditation: AccreditationDetails;
  contact: ContactInformation;
  emergency: EmergencyContact;
  operatingHours: OperatingHours;
  bedCapacity: BedCapacity;
  specialties: string[];
  branches: Branch[];
};

/** Seed values for the Hospital Profile tab -- mirrors the reference
 * screenshot exactly. Frontend-only mock (no `hospital_profile`-shaped
 * table/endpoint exists), same convention as GeneralSettingsTab -- Save/
 * Reset just reset this object. Hospital Name itself isn't duplicated here
 * (unlike the screenshot, which shows it as a free-text field): it's read
 * straight from the real, already-loaded `hospital.name`, same read-only
 * treatment the legacy settings page gives it. */
export function initialHospitalProfile(): HospitalProfileState {
  return {
    overview: {
      shortName: "DAAP",
      hospitalType: "Multi-Specialty Hospital",
      establishedYear: "2018",
      about:
        "DAAP CareConnect Hospital is committed to providing compassionate, quality healthcare with advanced " +
        "technology and patient-centric care. We strive for a healthier community through clinical excellence " +
        "and innovation.",
    },
    logoDataUrl: null,
    coverDataUrl: null,
    registration: {
      registrationNumber: "DL/2018/4421",
      licenseNumber: "HSP/ND/2024/7789",
      issuingAuthority: "Delhi Health Department",
      licenseValidTill: "31/12/2028",
      registrationDate: "05/04/2018",
    },
    accreditation: {
      accreditationBody: "National Accreditation Board for Hospitals (NABH)",
      accreditationNumber: "NABH-2023-1145",
      validTill: "14/08/2026",
    },
    contact: {
      phone: "+91 11 2345 6789",
      alternatePhone: "+91 11 2345 6790",
      email: "info@daapcareconnect.com",
      website: "www.daapcareconnect.com",
      address: "123 Health Avenue, Medical District\nNew Delhi, Delhi 110001, India",
    },
    emergency: {
      number: "+91 11 2345 6700",
      contactPerson: "Dr. Priya Sharma",
      designation: "Medical Superintendent",
    },
    operatingHours: {
      opdTimings: "9:00 AM - 6:00 PM",
      emergencyServices: "24 x 7 (Always Open)",
      pharmacyTimings: "8:00 AM - 10:00 PM",
      labServicesTimings: "8:00 AM - 8:00 PM",
    },
    bedCapacity: {
      totalBeds: 250,
      icuBeds: 40,
      generalBeds: 180,
      semiPrivateBeds: 20,
      privateRooms: 10,
    },
    specialties: [
      "General Medicine", "Cardiology", "Orthopedics", "Pediatrics",
      "Gynecology & Obstetrics", "Oncology", "Neurology", "Urology",
    ],
    branches: [
      { id: 1, name: "Main Hospital", location: "New Delhi, Delhi", type: "Main Campus", status: "Active" },
      { id: 2, name: "DAAP Care Center", location: "Greater Noida, UP", type: "Branch", status: "Active" },
      { id: 3, name: "DAAP Wellness Clinic", location: "Gurugram, Haryana", type: "Branch", status: "Active" },
    ],
  };
}

export const HOSPITAL_TYPE_OPTIONS = [
  "Multi-Specialty Hospital", "Single-Specialty Hospital", "General Hospital", "Clinic", "Diagnostic Center",
];

export const ACCREDITATION_BODY_OPTIONS = [
  "National Accreditation Board for Hospitals (NABH)",
  "Joint Commission International (JCI)",
  "ISO 9001:2015",
  "Not accredited",
];

export const OPD_TIMING_OPTIONS = ["9:00 AM - 6:00 PM", "8:00 AM - 8:00 PM", "10:00 AM - 5:00 PM"];
export const EMERGENCY_SERVICE_OPTIONS = ["24 x 7 (Always Open)", "OPD hours only", "Not available"];
export const PHARMACY_TIMING_OPTIONS = ["8:00 AM - 10:00 PM", "24 x 7 (Always Open)", "9:00 AM - 6:00 PM"];
export const LAB_TIMING_OPTIONS = ["8:00 AM - 8:00 PM", "24 x 7 (Always Open)", "9:00 AM - 6:00 PM"];

/** Extra picks for the "add a specialty" dropdown -- whatever isn't already
 * in the seed list above. */
export const ADDITIONAL_SPECIALTY_OPTIONS = [
  "Dermatology", "ENT (Otolaryngology)", "Nephrology", "Gastroenterology", "Pulmonology", "Psychiatry", "Endocrinology",
];
