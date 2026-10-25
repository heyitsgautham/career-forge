import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Eye, LayoutTemplate, Trash2 } from 'lucide-react';
import type { Template } from './types';

export function TemplateCard({
  template,
  isSystem = false,
  onPreview,
  onDelete,
}: {
  template: Template;
  isSystem?: boolean;
  onPreview?: () => void;
  onDelete?: () => void;
}) {
  return (
    <Card className="hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 overflow-hidden">
      {/* Preview */}
      <div className="h-48 bg-muted flex items-center justify-center border-b">
        {template.preview_image_path ? (
          <img
            src={template.preview_image_path}
            alt={template.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <LayoutTemplate className="h-16 w-16 text-muted-foreground/30" />
        )}
      </div>

      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <CardTitle className="text-base">{template.name}</CardTitle>
          {template.category && (
            <Badge variant="outline" className="text-xs">
              {template.category}
            </Badge>
          )}
        </div>
        <CardDescription className="line-clamp-2 text-xs">{template.description}</CardDescription>
      </CardHeader>

      <CardContent className="pt-0">
        <div className="flex justify-between items-center">
          <span className="text-xs text-muted-foreground">
            Used {template.use_count || 0} times
          </span>
          <div className="flex gap-1">
            <Button variant="ghost" size="sm" onClick={onPreview}>
              <Eye className="h-3 w-3" />
            </Button>
            {!isSystem && onDelete && (
              <Button variant="ghost" size="sm" className="text-destructive" onClick={onDelete}>
                <Trash2 className="h-3 w-3" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
