import type { TemplateListItem } from '@/lib/api/schemas';

/** A template as listed by GET /api/templates. The list omits latex_content. */
export type Template = TemplateListItem;
