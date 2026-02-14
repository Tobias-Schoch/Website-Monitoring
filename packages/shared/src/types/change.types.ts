import { z } from 'zod';

export enum ChangeType {
  CONTENT = 'CONTENT',
  FORM_DETECTED = 'FORM_DETECTED',
  KEYWORD_MATCH = 'KEYWORD_MATCH',
  STRUCTURE = 'STRUCTURE'
}

export enum Priority {
  INFO = 'INFO',
  IMPORTANT = 'IMPORTANT',
  CRITICAL = 'CRITICAL'
}

export const ChangeDetectionSchema = z.object({
  id: z.string().uuid(),
  checkId: z.string().uuid(),
  urlId: z.string().uuid(),
  type: z.nativeEnum(ChangeType),
  priority: z.nativeEnum(Priority),
  confidence: z.number().min(0).max(1),
  description: z.string(),
  diff: z.string().optional(),
  matchedKeywords: z.array(z.string()).optional(),
  detectedAt: z.date()
});

export type ChangeDetection = z.infer<typeof ChangeDetectionSchema>;

export interface ChangeComparisonResult {
  hasChanged: boolean;
  type: ChangeType | null;
  priority: Priority;
  confidence: number;
  description: string;
  diff?: string;
  matchedKeywords?: string[];
}

export interface FormDetection {
  id: string;
  changeId: string;
  formType: 'HTML' | 'PDF';
  formUrl: string;
  fields: FormField[];
  detectedAt: Date;
}

export interface FormField {
  name: string;
  type: string;
  label?: string;
  required: boolean;
  placeholder?: string;
}

export interface SemanticContent {
  texts: string[];
  images: ImageContent[];
  links: LinkContent[];
}

export interface ImageContent {
  src: string;
  alt: string;
}

export interface LinkContent {
  href: string;
}

export interface SemanticDiff {
  hasTextChanges: boolean;
  hasImageChanges: boolean;
  hasLinkChanges: boolean;
  changedTexts: string[];
  changedImages: ImageContent[];
  changedLinks: LinkContent[];
}
