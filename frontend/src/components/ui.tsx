import { forwardRef, useRef } from "react";
import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  KeyboardEvent as ReactKeyboardEvent,
  ReactNode,
} from "react";
import { LoaderCircle } from "lucide-react";

export function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "border border-transparent bg-accent text-on-accent shadow-sm hover:bg-accent-hover active:bg-accent-hover",
  secondary:
    "border border-line-strong bg-raised text-ink-soft hover:border-accent/35 hover:bg-sunken hover:text-ink",
  ghost:
    "border border-transparent text-muted hover:bg-ink/[0.05] hover:text-ink",
  danger:
    "border border-transparent bg-danger text-white shadow-sm hover:bg-danger-hover",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "min-h-11 gap-1.5 rounded-control px-2.5 text-label lg:min-h-8",
  md: "min-h-11 gap-2 rounded-control px-3.5 text-ui lg:min-h-10",
  lg: "min-h-11 gap-2 rounded-control px-4 text-ui",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: ButtonVariant;
    size?: ButtonSize;
  }
>(function Button(
  {
    variant = "primary",
    size = "md",
    className,
    children,
    type,
    ...props
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type || "button"}
      className={cx(
        "inline-flex items-center justify-center font-medium transition-[background-color,border-color,color,box-shadow] duration-150 disabled:pointer-events-none disabled:opacity-45",
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
});

export const IconButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { label: string }
>(function IconButton(
  { label, className, children, type, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type || "button"}
      aria-label={label}
      title={label}
      className={cx(
        "grid h-11 w-11 shrink-0 place-items-center rounded-control text-muted transition-[background-color,color] duration-150 hover:bg-ink/[0.05] hover:text-ink disabled:pointer-events-none disabled:opacity-40 lg:h-9 lg:w-9",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
});

type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger";

const badgeTones: Record<BadgeTone, string> = {
  neutral: "border-line-strong bg-sunken text-muted",
  accent: "border-accent/20 bg-accent-soft text-accent",
  success: "border-success-line bg-success-soft text-success",
  warning: "border-warning-line bg-warning-soft text-warning",
  danger: "border-danger-line bg-danger-soft text-danger",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cx(
        "inline-flex min-h-5 items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        badgeTones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const dotTones: Record<BadgeTone, string> = {
  neutral: "bg-muted",
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
};

export function Dot({
  tone = "neutral",
  pulse = false,
  className,
}: {
  tone?: BadgeTone;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "inline-block h-2 w-2 shrink-0 rounded-full",
        dotTones[tone],
        pulse && "pulse-dot",
        className,
      )}
    />
  );
}

export function Spinner({
  size = 16,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <LoaderCircle
      size={size}
      className={cx("animate-spin", className)}
      aria-hidden="true"
    />
  );
}

export const inputClass =
  "h-11 w-full rounded-control border border-line-strong bg-raised px-3 text-base text-ink outline-none transition-[border-color,box-shadow] placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-50 lg:h-10 lg:text-ui";

export const textareaClass =
  "w-full resize-none rounded-control border border-line-strong bg-raised px-3 py-2.5 text-base leading-relaxed text-ink outline-none transition-[border-color,box-shadow] placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-50 lg:text-ui";

export const selectClass =
  "h-11 w-full appearance-none rounded-control border border-line-strong bg-raised px-3 pr-9 text-base font-normal text-ink outline-none transition-[border-color,box-shadow] focus:border-accent focus:ring-2 focus:ring-accent/15 lg:h-10 lg:text-ui";

export function Field({
  label,
  htmlFor,
  hint,
  error,
  optional,
  className,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: ReactNode;
  error?: string | null;
  optional?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cx("min-w-0", className)}>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <label
          htmlFor={htmlFor}
          className="text-label font-medium text-ink-soft"
        >
          {label}
          {optional && (
            <span className="ml-1 font-normal text-muted">(optional)</span>
          )}
        </label>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </div>
      {children}
      {error && (
        <p
          id={htmlFor ? `${htmlFor}-error` : undefined}
          role="alert"
          className="mt-1.5 text-xs font-medium leading-relaxed text-danger"
        >
          {error}
        </p>
      )}
    </div>
  );
}

const alertTones: Record<BadgeTone, string> = {
  neutral: "border-line-strong bg-sunken text-ink-soft",
  accent: "border-accent/20 bg-accent-soft text-accent",
  success: "border-success-line bg-success-soft text-success",
  warning: "border-warning-line bg-warning-soft text-warning",
  danger: "border-danger-line bg-danger-soft text-danger",
};

export function InlineAlert({
  tone = "neutral",
  icon,
  className,
  children,
}: {
  tone?: BadgeTone;
  icon?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        "flex items-start gap-2.5 rounded-card border px-3.5 py-3 text-label leading-relaxed",
        alertTones[tone],
        className,
      )}
    >
      {icon && <span className="mt-0.5 shrink-0">{icon}</span>}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-card border border-dashed border-line-strong bg-sunken/70 px-5 py-8 text-center",
        className,
      )}
    >
      {icon && (
        <span className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-raised text-muted shadow-sm">
          {icon}
        </span>
      )}
      <div className="mt-3 text-ui font-semibold text-ink">{title}</div>
      {description && (
        <p className="mx-auto mt-1 max-w-sm text-label leading-relaxed text-muted">
          {description}
        </p>
      )}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function Skeleton({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cx("skeleton", className)}
      {...props}
    />
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-line-strong bg-raised px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
      {children}
    </kbd>
  );
}

export type SegmentOption<T extends string> = {
  value: T;
  label: string;
  icon?: ReactNode;
  count?: number;
  testId?: string;
};

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
  compact = false,
}: {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
  compact?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  function handleKeyDown(
    event: ReactKeyboardEvent<HTMLElement>,
    index: number,
  ) {
    if (
      event.key !== "ArrowLeft" &&
      event.key !== "ArrowRight" &&
      event.key !== "Home" &&
      event.key !== "End"
    ) {
      return;
    }
    event.preventDefault();
    const nextIndex =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? options.length - 1
          : event.key === "ArrowRight"
            ? (index + 1) % options.length
            : (index - 1 + options.length) % options.length;
    const next = options[nextIndex];
    onChange(next.value);
    const buttons = ref.current?.querySelectorAll<HTMLButtonElement>(
      '[data-segment="true"]',
    );
    buttons?.[nextIndex]?.focus();
  }

  return (
    <div
      ref={ref}
      role="group"
      aria-label={label}
      className={cx(
        "inline-flex min-h-11 items-center gap-0.5 rounded-card border border-line bg-surface/95 p-1 shadow-card backdrop-blur-sm lg:min-h-10",
        className,
      )}
    >
      {options.map((option, index) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            data-segment="true"
            data-testid={option.testId}
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            className={cx(
              "inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-control px-3 text-label font-medium transition-[background-color,color] lg:min-h-8",
              compact && "px-2.5",
              active
                ? "bg-accent text-on-accent shadow-sm"
                : "text-muted hover:bg-ink/[0.05] hover:text-ink",
            )}
          >
            {option.icon}
            <span>{option.label}</span>
            {typeof option.count === "number" && option.count > 0 && (
              <span
                className={cx(
                  "grid h-5 min-w-5 place-items-center rounded-full px-1 text-xs font-semibold tabular-nums",
                  active
                    ? "bg-white/20 text-white"
                    : "bg-sunken text-muted",
                )}
              >
                {option.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
