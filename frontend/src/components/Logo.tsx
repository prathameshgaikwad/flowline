import { cx } from "./ui";

export function Logo({
  size = 28,
  withWord = false,
  className,
}: {
  size?: number;
  withWord?: boolean;
  className?: string;
}) {
  return (
    <span className={cx("inline-flex items-center gap-2", className)}>
      <span
        className="grid shrink-0 place-items-center rounded-[9px] bg-accent text-white shadow-sm"
        style={{ width: size, height: size }}
      >
        <svg
          width={size * 0.62}
          height={size * 0.62}
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M7 17V9.5A2.5 2.5 0 0 1 9.5 7H17"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinecap="round"
          />
          <circle cx="7" cy="17" r="2.1" fill="currentColor" />
          <circle cx="17" cy="7" r="2.1" fill="currentColor" />
        </svg>
      </span>
      {withWord && (
        <span className="text-ui font-semibold tracking-[-0.02em] text-ink">
          Flowline
        </span>
      )}
    </span>
  );
}
