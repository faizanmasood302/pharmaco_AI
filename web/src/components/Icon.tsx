import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & {
  name: string;
};

const PATHS: Record<string, string> = {
  account_circle: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4 0-7 2-7 4.5V20h14v-1.5C19 16 16 14 12 14Z",
  account_tree: "M6 4h5v5H9v2h6V9h-2V4h5v5h-3v2h3v5h-5v-3H9v3H4v-5h3V9H4V4h2Z",
  analytics: "M4 19h16v2H4v-2Zm2-2V9h3v8H6Zm5 0V4h3v13h-3Zm5 0v-6h3v6h-3Z",
  assignment_ind: "M5 3h14v18H5V3Zm4 4a3 3 0 1 0 6 0 3 3 0 0 0-6 0Zm-1 10h8c-.4-2-2-3-4-3s-3.6 1-4 3Z",
  biotech: "M7 3h10v2h-4v3l5 8a4 4 0 0 1-3.4 6H9.4A4 4 0 0 1 6 16l5-8V5H7V3Zm3 12h4l-2-3.2L10 15Z",
  check_circle: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-1.2 14.2-3.5-3.5 1.4-1.4 2.1 2.1 4.5-4.6 1.4 1.4-5.9 6Z",
  close: "m6.4 5 5.6 5.6L17.6 5 19 6.4 13.4 12l5.6 5.6-1.4 1.4-5.6-5.6L6.4 19 5 17.6l5.6-5.6L5 6.4 6.4 5Z",
  description: "M6 2h9l5 5v15H6V2Zm8 1.5V8h4.5L14 3.5ZM8 12h8v2H8v-2Zm0 4h8v2H8v-2Z",
  expand_more: "m7 10 5 5 5-5H7Z",
  help: "M11 18h2v-2h-2v2Zm1-16a7 7 0 0 0-7 7h2a5 5 0 1 1 8.5 3.5l-1.5 1.4c-.8.7-1 1.3-1 2.1h-2c0-1.6.5-2.6 1.6-3.5l1.4-1.2A3.2 3.2 0 0 0 12 6a3 3 0 0 0-3 3H7a5 5 0 0 1 5-5Z",
  history: "M12 4a8 8 0 1 1-7.4 5H2l3.5-4L9 9H6.7A6 6 0 1 0 12 6v5l4 2-.9 1.8L10 12V4h2Z",
  info: "M11 17h2v-6h-2v6Zm0-8h2V7h-2v2Zm1-7a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z",
  insights: "M4 18h16v2H4v-2Zm1-2 4-7 4 4 4-8 3 11h-2.1l-1.5-5.5-2.7 5.4-4.2-4.2L7.3 16H5Z",
  medication: "M8.5 3a5.5 5.5 0 0 1 3.9 9.4l-4 4A5.5 5.5 0 0 1 .6 8.6l4-4A5.5 5.5 0 0 1 8.5 3Zm6.9 5.6 4 4a5.5 5.5 0 0 1-7.8 7.8l-2-2 5.8-5.8a7.4 7.4 0 0 0 0-4Z",
  menu_book: "M4 4.5C5.2 3.6 7 3 9 3c1.3 0 2.7.3 4 .9V20c-1.2-.6-2.6-.9-4-.9-2 0-3.8.6-5 1.5V4.5Zm16 0v16.1c-1.2-.9-3-1.5-5-1.5V3c2 0 3.8.6 5 1.5Z",
  notifications: "M12 22a2.5 2.5 0 0 0 2.4-2h-4.8A2.5 2.5 0 0 0 12 22Zm7-6-2-2V9a5 5 0 0 0-4-4.9V2h-2v2.1A5 5 0 0 0 7 9v5l-2 2v1h14v-1Z",
  print: "M6 9V3h12v6H6Zm0 8H4v-6h16v6h-2v4H6v-4Zm2 2h8v-5H8v5Z",
  progress_activity: "M12 2v3a7 7 0 1 1-7 7H2a10 10 0 1 0 10-10Z",
  report_problem: "M1 21h22L12 2 1 21Zm12-3h-2v-2h2v2Zm0-4h-2v-4h2v4Z",
  science: "M8 2h8v2h-2v5.2l5 8.6A3 3 0 0 1 16.4 22H7.6A3 3 0 0 1 5 17.8l5-8.6V4H8V2Zm1 14h6l-3-5-3 5Z",
  search: "M10 4a6 6 0 1 0 3.7 10.7l4.3 4.3 1.4-1.4-4.3-4.3A6 6 0 0 0 10 4Zm0 2a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z",
  settings: "M19.4 13.5a7.7 7.7 0 0 0 0-3l2-1.5-2-3.4-2.4 1a7.5 7.5 0 0 0-2.6-1.5L14 2h-4l-.4 3.1A7.5 7.5 0 0 0 7 6.6l-2.4-1-2 3.4 2 1.5a7.7 7.7 0 0 0 0 3l-2 1.5 2 3.4 2.4-1a7.5 7.5 0 0 0 2.6 1.5L10 22h4l.4-3.1a7.5 7.5 0 0 0 2.6-1.5l2.4 1 2-3.4-2-1.5ZM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Z",
  swap_horiz: "M7 7h11l-3-3 1.4-1.4L22 8l-5.6 5.4L15 12l3-3H7V7Zm10 10H6l3 3-1.4 1.4L2 16l5.6-5.4L9 12l-3 3h11v2Z",
  timer: "M9 1h6v2H9V1Zm2 11V7h2v6l4 2-.8 1.8L11 14v-2Zm1-8a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z",
  verified_user: "M12 2 5 5v6c0 4.4 3 8.5 7 10 4-1.5 7-5.6 7-10V5l-7-3Zm-1 13.5-3-3 1.4-1.4 1.6 1.6 4.6-4.6L17 9.5l-6 6Z",
  warning: "M1 21h22L12 2 1 21Zm12-3h-2v-2h2v2Zm0-4h-2v-4h2v4Z",
};

export default function Icon({ name, className, ...props }: IconProps) {
  const path = PATHS[name] ?? PATHS.info;

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="currentColor"
      focusable="false"
      viewBox="0 0 24 24"
      {...props}
    >
      <path d={path} />
    </svg>
  );
}
