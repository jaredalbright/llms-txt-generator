import { marked } from 'marked';

const renderer = new marked.Renderer();
renderer.link = ({ href, text }) => {
  return `<a href="${href}" target="_blank" rel="noopener noreferrer">${text}</a>`;
};

marked.setOptions({
  gfm: true,
  breaks: false,
  renderer,
});

export function renderMarkdown(content: string): string {
  return marked.parse(content) as string;
}
