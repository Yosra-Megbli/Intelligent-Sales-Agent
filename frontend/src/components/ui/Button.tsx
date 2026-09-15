import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "outline";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", isLoading = false, children, disabled, ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium transition-smooth rounded-[0.75rem] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-green)] disabled:opacity-50 disabled:pointer-events-none select-none cursor-pointer";

    const variants = {
      primary:
        "bg-[var(--brand-green)] text-white hover:bg-[var(--brand-hover)] shadow-sm active:scale-[0.98]",
      secondary:
        "bg-[var(--surface)] text-[var(--ink)] border border-[var(--border)] hover:bg-[var(--surface-hover)] hover:border-[var(--border-hover)] shadow-sm",
      outline:
        "border border-[var(--border)] text-[var(--ink)] hover:bg-[var(--brand-soft)] hover:text-[var(--brand-green)] hover:border-[var(--brand-soft-border)]",
      ghost:
        "text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--brand-soft)]",
      danger:
        "bg-[var(--danger-red)] text-white hover:opacity-90 shadow-sm active:scale-[0.98]",
    };

    const sizes = {
      sm: "h-8 px-3 text-xs gap-1.5",
      md: "h-9 px-4 text-sm gap-2",
      lg: "h-11 px-5 text-base gap-2.5",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        {...props}
      >
        {isLoading ? (
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
            <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse [animation-delay:200ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse [animation-delay:400ms]" />
          </span>
        ) : (
          children
        )}
      </button>
    );
  }
);

Button.displayName = "Button";
