export interface Resume {
  id: string;
  name: string;
  template_id?: string;
  job_description_id?: string;
  job_id?: string;
  type?: string;
  status: 'draft' | 'generating' | 'generated' | 'compiling' | 'compiled' | 'error';
  pdf_path?: string;
  latex_content?: string;
  error_message?: string;
  analysis?: string;
  tex_s3_key?: string;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: string;
  title: string;
  company: string;
}

export interface Template {
  id: string;
  name: string;
}
