# SCG New JCMS theme inspection

Inspected reference: `C:/Users/DELL/Desktop/SCG_New_JCMS`.

Read before frontend implementation: `tailwind.config.js`, `src/index.css`,
`src/App.tsx`, `src/main.tsx`, `src/components/Sidebar.tsx`, `Header.tsx`,
`Modal.tsx`, `src/pages/Dashboard.tsx`, and `src/pages/Company.tsx`.

The reference extends no Tailwind color, font, or radius tokens. Its typography
is Tailwind's default system sans-serif, not a separately installed web font.

| Element | Reference convention retained |
| --- | --- |
| Application shell | `flex h-screen bg-slate-200 overflow-hidden` |
| Sidebar | White, 240px (`w-60`), 64px collapsed, gray-200 right border |
| Navigation | 13–14px, rounded-lg, active blue-900 with white text |
| Group labels | 12px uppercase, gray-500, semibold, wide tracking |
| Header | White, gray-200 bottom border, px-6 py-3.5, title 20px bold |
| Main content | p-6, space-y-6, independently scrolling |
| Cards | White, rounded-xl, border-gray-100, shadow-sm |
| Primary buttons | bg-blue-900 hover:bg-blue-950, white, rounded-lg |
| Secondary controls | White/gray-50, gray-200 border, rounded-lg |
| Statuses | Emerald success, amber caution, red danger, pill badges |
| Dialogs | Rounded-xl, shadow-xl, black/40 backdrop with blur |
| Dark mode | Root `.dark`, #0b1520 canvas, #0f1923 cards, #334155 borders |
| Icons | lucide-react 0.344.0, generally 14–20px |

`frontend/src/index.css` copies the reference's complete Tailwind directives,
scrollbars, and dark-mode overrides. The JTMX icon and logo are copied from the
reference's public images. No reference business data, credentials, or mock
records are copied. Application pages, controls, and notifications use real
backend data rather than reference dashboard placeholders.
