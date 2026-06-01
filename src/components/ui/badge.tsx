import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "error" | "warning";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300",
    success: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    error: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    warning: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
