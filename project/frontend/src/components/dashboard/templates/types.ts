export interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  is_system: boolean;
  use_count: number;
  latex_content: string;
  preview_image?: string;
  created_at: string;
}
