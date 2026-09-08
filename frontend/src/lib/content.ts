import raw from "../data/content.generated.json";

export interface ContentSection {
  heading: string;
  text: string;
}

export interface ContentDoc {
  id: string;
  section: string;
  title: string;
  type: string;
  domain: string;
  date: string;
  repo: string;
  status: string;
  images: string[];
  volunteer: boolean;
  sections: ContentSection[];
}

export const CONTENT = raw as { generatedAt: string; documents: ContentDoc[] };

export function docsBySection(section: string): ContentDoc[] {
  return CONTENT.documents.filter((d) => d.section === section);
}
