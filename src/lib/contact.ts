export const CONTACT = {
  email: "info@daaprimeprojects.com",
  phone: "+91 98765 43210",
  phoneFormatted: "+91 98765 43210",
} as const;

export const CONTACT_LINKS = {
  email: `mailto:${CONTACT.email}`,
  phone: `tel:${CONTACT.phone.replace(/\s+/g, "")}`,
} as const;
