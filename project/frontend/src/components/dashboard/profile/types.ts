export interface ExperienceEntry {
  company: string;
  title: string;
  dates: string;
  location?: string;
  highlights: string[];
}

export interface EducationEntry {
  school: string;
  degree: string;
  field: string;
  dates: string;
  location?: string;
  gpa?: string;
}

export interface CertificationEntry {
  name: string;
  issuer: string;
  date: string;
  credential_id?: string;
  url?: string;
}

export interface ProfileData {
  id: string;
  email: string;
  name?: string;
  headline?: string;
  summary?: string;
  location?: string;
  phone?: string;
  website?: string;
  linkedin_url?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  country?: string;
  institution?: string;
  degree?: string;
  field_of_study?: string;
  graduation_year?: string;
  experience?: ExperienceEntry[];
  education?: EducationEntry[];
  skills?: string[];
  certifications?: CertificationEntry[];
  achievements?: string[];
}

export type ProfileField = keyof ProfileData;
export type ProfileChangeHandler = (field: ProfileField, value: any) => void;

export interface IngestionSummary {
  total: number;
  processed: number;
  failed: number;
  lastRunAt: string;
}
