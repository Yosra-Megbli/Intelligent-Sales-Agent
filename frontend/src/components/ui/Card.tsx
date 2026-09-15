import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export const Card: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => {
  return (
    <div
      className={cn(
        "bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] shadow-xs text-[var(--ink)] overflow-hidden transition-smooth",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => {
  return (
    <div className={cn("p-5 border-b border-[var(--border)]", className)} {...props}>
      {children}
    </div>
  );
};

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({ className, children, ...props }) => {
  return (
    <h3 className={cn("font-semibold text-base tracking-tight text-[var(--ink)]", className)} {...props}>
      {children}
    </h3>
  );
};

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <p className={cn("text-xs text-[var(--ink-muted)] mt-1", className)} {...props}>
      {children}
    </p>
  );
};

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => {
  return (
    <div className={cn("p-5", className)} {...props}>
      {children}
    </div>
  );
};

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => {
  return (
    <div className={cn("p-4 bg-[var(--surface-hover)] border-t border-[var(--border)] flex items-center", className)} {...props}>
      {children}
    </div>
  );
};
