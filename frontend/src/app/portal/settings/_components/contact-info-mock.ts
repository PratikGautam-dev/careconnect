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

/** Seed values for the combined Contact Information card on the General tab
 * (formerly part of the now-deleted Hospital Profile tab). Frontend-only
 * mock -- no `hospital_profile`-shaped table/endpoint exists. */
export function initialContactInformation(): ContactInformation {
  return {
    phone: "+91 11 2345 6789",
    alternatePhone: "+91 11 2345 6790",
    email: "info@daapcareconnect.com",
    website: "www.daapcareconnect.com",
    address: "123 Health Avenue, Medical District\nNew Delhi, Delhi 110001, India",
  };
}

export function initialEmergencyContact(): EmergencyContact {
  return {
    number: "+91 11 2345 6700",
    contactPerson: "Dr. Priya Sharma",
    designation: "Medical Superintendent",
  };
}
