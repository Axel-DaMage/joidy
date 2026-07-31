<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { Editor } from '@tiptap/core';
  import StarterKit from '@tiptap/starter-kit';
  import Link from '@tiptap/extension-link';
  import Image from '@tiptap/extension-image';
  import Placeholder from '@tiptap/extension-placeholder';
  import TaskList from '@tiptap/extension-task-list';
  import TaskItem from '@tiptap/extension-task-item';
  import Underline from '@tiptap/extension-underline';
  import { marked } from 'marked';
  import TurndownService from 'turndown';
  import DOMPurify from 'dompurify';

  const dispatch = createEventDispatcher<{
    contentchange: string;
    save: void;
  }>();

  interface Props {
    content: string;
    placeholder?: string;
    oncontentchange?: (e: CustomEvent<string>) => void;
    onsave?: (e: CustomEvent<void>) => void;
  }

  let { content = '', placeholder = 'Escribe algo...', oncontentchange, onsave }: Props = $props();

  let editor: Editor | null = null;
  let editorElement: HTMLElement | null = null;

  const turndown = new TurndownService({
    headingStyle: 'atx',
    codeBlockStyle: 'fenced',
    bulletListMarker: '-',
  });

  // Convert markdown → HTML for TipTap
  function markdownToHtml(md: string): string {
    if (!md.trim()) return '';
    const html = marked.parse(md, { gfm: true, breaks: true });
    return DOMPurify.sanitize(String(html));
  }

  // Convert TipTap HTML → markdown
  function htmlToMarkdown(html: string): string {
    return turndown.turndown(html);
  }

  onMount(() => {
    if (!editorElement) return;

    editor = new Editor({
      element: editorElement,
      extensions: [
        StarterKit.configure({
          codeBlock: false,
        }),
        Underline,
        Link.configure({
          openOnClick: false,
          HTMLAttributes: { class: 'tiptap-link' },
        }),
        Image.configure({
          inline: false,
          HTMLAttributes: { class: 'tiptap-image' },
        }),
        Placeholder.configure({ placeholder }),
        TaskList,
        TaskItem.configure({ nested: true }),
      ],
      content: markdownToHtml(content),
      onUpdate: ({ editor }) => {
        const md = htmlToMarkdown(editor.getHTML());
        dispatch('contentchange', md);
      },
      editorProps: {
        attributes: {
          class: 'tiptap-prose',
          spellcheck: 'false',
        },
        handleKeyDown: (_view, event) => {
          if ((event.ctrlKey || event.metaKey) && event.key === 's') {
            event.preventDefault();
            dispatch('save');
            return true;
          }
          return false;
        },
      },
    });
  });

  // Sync external content changes (e.g. note switch)
  $effect(() => {
    if (editor && content !== undefined) {
      const currentMd = htmlToMarkdown(editor.getHTML());
      if (currentMd !== content) {
        editor.commands.setContent(markdownToHtml(content), { emitUpdate: false });
      }
    }
  });

  onDestroy(() => {
    editor?.destroy();
    editor = null;
  });

  // Toolbar actions
  export function toggleBold() { editor?.chain().focus().toggleBold().run(); }
  export function toggleItalic() { editor?.chain().focus().toggleItalic().run(); }
  export function toggleUnderline() { editor?.chain().focus().toggleUnderline().run(); }
  export function toggleStrike() { editor?.chain().focus().toggleStrike().run(); }
  export function toggleH1() { editor?.chain().focus().toggleHeading({ level: 1 }).run(); }
  export function toggleH2() { editor?.chain().focus().toggleHeading({ level: 2 }).run(); }
  export function toggleH3() { editor?.chain().focus().toggleHeading({ level: 3 }).run(); }
  export function toggleBulletList() { editor?.chain().focus().toggleBulletList().run(); }
  export function toggleOrderedList() { editor?.chain().focus().toggleOrderedList().run(); }
  export function toggleTaskList() { editor?.chain().focus().toggleTaskList().run(); }
  export function toggleBlockquote() { editor?.chain().focus().toggleBlockquote().run(); }
  export function toggleCodeBlock() { editor?.chain().focus().toggleCodeBlock().run(); }
  export function setLink(url: string) {
    if (url === '') {
      editor?.chain().focus().unsetLink().run();
    } else {
      editor?.chain().focus().setLink({ href: url }).run();
    }
  }
  export function insertImage(src: string, alt: string = '') {
    editor?.chain().focus().setImage({ src, alt }).run();
  }
  export function insertContent(text: string) {
    const html = markdownToHtml(text);
    editor?.chain().focus().insertContent(html).run();
  }
</script>

<div bind:this={editorElement} class="wysiwyg-editor"></div>

<style>
  :global(.wysiwyg-editor .tiptap-prose) {
    outline: none;
    min-height: 300px;
    padding: 16px 20px;
    font-size: 14px;
    line-height: 1.7;
    color: var(--text-primary);
  }

  :global(.wysiwyg-editor .tiptap-prose:empty::before) {
    content: attr(data-placeholder);
    color: var(--text-muted);
    pointer-events: none;
    float: left;
    height: 0;
  }

  :global(.wysiwyg-editor .tiptap-prose h1) {
    font-size: 1.5em;
    font-weight: 700;
    margin: 0.8em 0 0.4em;
    color: var(--md-h1, var(--xp));
  }

  :global(.wysiwyg-editor .tiptap-prose h2) {
    font-size: 1.3em;
    font-weight: 600;
    margin: 0.7em 0 0.3em;
    color: var(--md-h2, var(--xp));
  }

  :global(.wysiwyg-editor .tiptap-prose h3) {
    font-size: 1.15em;
    font-weight: 600;
    margin: 0.6em 0 0.3em;
    color: var(--md-h3, var(--xp));
  }

  :global(.wysiwyg-editor .tiptap-prose p) {
    margin: 0.4em 0;
  }

  :global(.wysiwyg-editor .tiptap-prose ul),
  :global(.wysiwyg-editor .tiptap-prose ol) {
    padding-left: 1.5em;
    margin: 0.4em 0;
  }

  :global(.wysiwyg-editor .tiptap-prose ul) {
    list-style: disc;
  }

  :global(.wysiwyg-editor .tiptap-prose ol) {
    list-style: decimal;
  }

  :global(.wysiwyg-editor .tiptap-prose ul[data-type="taskList"]) {
    list-style: none;
    padding-left: 0;
  }

  :global(.wysiwyg-editor .tiptap-prose ul[data-type="taskList"] li) {
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }

  :global(.wysiwyg-editor .tiptap-prose ul[data-type="taskList"] li > label) {
    flex-shrink: 0;
    user-select: none;
  }

  :global(.wysiwyg-editor .tiptap-prose blockquote) {
    border-left: 3px solid var(--border);
    padding-left: 12px;
    margin: 0.6em 0;
    color: var(--text-secondary);
    font-style: italic;
  }

  :global(.wysiwyg-editor .tiptap-prose pre) {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 12px 16px;
    overflow-x: auto;
    font-family: var(--font-mono);
    font-size: 13px;
    margin: 0.6em 0;
  }

  :global(.wysiwyg-editor .tiptap-prose code) {
    background: var(--elevated);
    border-radius: 3px;
    padding: 0 4px;
    font-family: var(--font-mono);
    font-size: 0.9em;
    color: var(--md-h1, var(--xp));
  }

  :global(.wysiwyg-editor .tiptap-prose pre code) {
    background: none;
    padding: 0;
  }

  :global(.wysiwyg-editor .tiptap-prose a.tiptap-link) {
    color: var(--md-h2, var(--xp));
    text-decoration: underline;
    cursor: pointer;
  }

  :global(.wysiwyg-editor .tiptap-prose img.tiptap-image) {
    max-width: 100%;
    border-radius: var(--r);
    margin: 0.6em 0;
  }

  :global(.wysiwyg-editor .tiptap-prose hr) {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1em 0;
  }

  :global(.wysiwyg-editor .tiptap-prose strong) {
    font-weight: 700;
    color: var(--text-primary);
  }

  :global(.wysiwyg-editor .tiptap-prose em) {
    font-style: italic;
    color: var(--text-secondary);
  }
</style>
