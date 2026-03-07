'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, Bot, User, CheckCircle, RefreshCw, AlertCircle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { resumesApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { LatexDiffViewer } from '@/components/resume-editor/latex-diff-viewer';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  pendingLatex?: string | null;   // AI-proposed full .tex
  originalLatex?: string;          // snapshot of editor at send time
  appliedLatex?: boolean;
  rejectedLatex?: boolean;
  isStreaming?: boolean;
  error?: boolean;
}

interface AiChatDrawerProps {
  resumeId: string;
  getLatex: () => string;
  onApplyLatex: (latex: string) => void;
}

/**
 * AI chat drawer for the resume editor.
 * Streams SSE from POST /api/resumes/{id}/ai-edit and shows Apply Changes button.
 */
export function AiChatDrawer({ resumeId, getLatex, onApplyLatex }: AiChatDrawerProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const appendToAssistant = useCallback((id: string, chunk: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, text: m.text + chunk } : m,
      ),
    );
  }, []);

  const finalizeAssistant = useCallback((id: string, pendingLatex: string | null, fullText: string) => {
    // The server guarantees no <latex> leaks, but trim as a last-resort safety net.
    const cleanText = fullText.replace(/<latex[\s\S]*/i, '').trimEnd();
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, text: cleanText, isStreaming: false, pendingLatex } : m,
      ),
    );
  }, []);

  const handleSend = useCallback(async () => {
    const message = input.trim();
    if (!message || isStreaming) return;

    const userMsgId = `user-${Date.now()}`;
    const assistantMsgId = `assistant-${Date.now()}`;

    const currentLatex = getLatex();

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', text: message },
      { id: assistantMsgId, role: 'assistant', text: '', isStreaming: true, pendingLatex: null, originalLatex: currentLatex },
    ]);
    setInput('');
    setIsStreaming(true);

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      const response = await resumesApi.aiEdit(resumeId, message, currentLatex);
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let collectedLatex: string | null = null;
      let fullText = '';  // accumulate for finalize cleanup

      while (true) {
        const { done, value } = await reader.read();
        if (done || abort.signal.aborted) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const rawData = line.slice(6).trim();
            if (!rawData || rawData === '{}') continue;
            try {
              const parsed = JSON.parse(rawData);
              if (parsed.text !== undefined) {
                // Server guarantees this is clean conversational text only
                fullText += parsed.text as string;
                appendToAssistant(assistantMsgId, parsed.text as string);
              }
              if (parsed.latex !== undefined) {
                collectedLatex = parsed.latex;
              }
            } catch {
              // SSE comment or non-JSON line
            }
          }
        }
      }

      finalizeAssistant(assistantMsgId, collectedLatex, fullText);
    } catch (err) {
      if (!abort.signal.aborted) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, isStreaming: false, text: 'Something went wrong. Please try again.', error: true }
              : m,
          ),
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [input, isStreaming, resumeId, getLatex, appendToAssistant, finalizeAssistant]);

  const handleApply = useCallback(
    (msgId: string, latex: string) => {
      onApplyLatex(latex);
      setMessages((prev) =>
        prev.map((m) => (m.id === msgId ? { ...m, appliedLatex: true, pendingLatex: null } : m)),
      );
    },
    [onApplyLatex],
  );

  const handleReject = useCallback((msgId: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId ? { ...m, rejectedLatex: true, pendingLatex: null } : m)),
    );
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  const handleReset = () => {
    abortRef.current?.abort();
    setMessages([]);
    setInput('');
    setIsStreaming(false);
  };

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/50 shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-violet-500" />
          <span className="text-sm font-medium">AI Resume Assistant</span>
          <span className="text-xs text-muted-foreground">powered by Claude</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 gap-1 text-xs text-muted-foreground"
          onClick={handleReset}
        >
          <RefreshCw className="h-3 w-3" />
          Reset chat
        </Button>
      </div>

      {/* Message history */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground py-4 gap-2">
            <Bot className="h-8 w-8 opacity-20" />
            <div>
              <p className="text-sm font-medium">Ask Claude to improve your resume</p>
              <p className="text-xs opacity-70 mt-1">
                E.g. "Make the summary more concise" or "Add stronger action verbs"
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'flex gap-2',
              msg.role === 'user' ? 'justify-end' : 'justify-start',
            )}
          >
            {msg.role === 'assistant' && (
              <div className="h-6 w-6 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="h-3.5 w-3.5 text-violet-600 dark:text-violet-400" />
              </div>
            )}

            <div
              className={cn(
                'max-w-[85%] rounded-xl px-3 py-2 text-sm',
                msg.role === 'user'
                  ? 'bg-violet-600 text-white rounded-tr-sm'
                  : 'bg-muted rounded-tl-sm',
                msg.error && 'bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400',
              )}
            >
              {/* Message text */}
              <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>

              {/* Streaming indicator */}
              {msg.isStreaming && (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground mt-1">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Thinking…
                </span>
              )}

              {/* Diff view + Accept / Reject */}
              {!msg.isStreaming && msg.pendingLatex && !msg.appliedLatex && !msg.rejectedLatex && (
                <div className="mt-2">
                  <LatexDiffViewer
                    original={msg.originalLatex ?? ''}
                    modified={msg.pendingLatex}
                  />
                  <div className="mt-2 flex gap-2">
                    <Button
                      size="sm"
                      className="h-7 text-xs gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                      onClick={() => handleApply(msg.id, msg.pendingLatex!)}
                    >
                      <CheckCircle className="h-3 w-3" />
                      Accept
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs gap-1.5 text-red-500 border-red-300 hover:bg-red-50 dark:hover:bg-red-950/20"
                      onClick={() => handleReject(msg.id)}
                    >
                      <X className="h-3 w-3" />
                      Reject
                    </Button>
                  </div>
                </div>
              )}

              {/* Applied indicator */}
              {msg.appliedLatex && (
                <div className="mt-1 flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                  <CheckCircle className="h-3 w-3" />
                  Applied to editor
                </div>
              )}

              {/* Rejected indicator */}
              {msg.rejectedLatex && (
                <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                  <X className="h-3 w-3" />
                  Changes rejected
                </div>
              )}

              {/* Error icon */}
              {msg.error && (
                <AlertCircle className="h-3.5 w-3.5 text-red-500 mt-1" />
              )}
            </div>

            {msg.role === 'user' && (
              <div className="h-6 w-6 rounded-full bg-violet-600 flex items-center justify-center shrink-0 mt-0.5">
                <User className="h-3.5 w-3.5 text-white" />
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-3 pb-3 pt-2 border-t bg-muted/20 shrink-0">
        <div className="flex gap-2 items-end">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Claude to improve your resume… (Ctrl+Enter to send)"
            className="flex-1 min-h-[60px] max-h-[120px] resize-none text-sm"
            disabled={isStreaming}
          />
          <Button
            size="icon"
            className="h-10 w-10 shrink-0 bg-violet-600 hover:bg-violet-700"
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1.5 ml-0.5">
          Claude will explain changes and show an Apply button for the updated LaTeX.{' '}
          <kbd className="px-1 py-0.5 rounded border text-[10px] font-mono">Ctrl+Enter</kbd> to send.
        </p>
      </div>
    </div>
  );
}
