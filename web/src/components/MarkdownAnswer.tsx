// Markdown 答案渲染（react-markdown + remark-gfm）。

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownAnswer({ content, className = "" }: { content: string; className?: string }) {
  if (!content) {
    return <div className="text-sm text-slate-400">（暂无内容）</div>;
  }
  return (
    <div
      className={`prose prose-sm prose-slate max-w-none dark:prose-invert ${className}`}
      data-testid="markdown-answer"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
