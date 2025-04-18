"use client";

import clsx from "clsx";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface ToastOptions {
  message: string;
  variant?: "info" | "warn" | "error" | "success";
}

interface ToastContextValue {
  showToast: (options: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue>(0 as never);

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toastOptions, setToastOptions] = useState<
    (ToastOptions & { id: number })[]
  >([]);

  const showToast = useCallback((inputOptions: ToastOptions) => {
    const options = { ...inputOptions, id: Math.random() };
    setToastOptions((prev) => prev.concat(options));

    setTimeout(() => {
      setToastOptions((prev) => prev.filter((p) => p !== options));
    }, 8000);
  }, []);

  const value = useMemo<ToastContextValue>(() => {
    return {
      showToast,
    };
  }, [showToast]);

  return (
    <ToastContext value={value}>
      {children}

      {toastOptions.length ? (
        <div className="toast z-50">
          {toastOptions.map(({ id, message, variant }) => (
            <div
              key={id}
              className={clsx(
                "alert",
                variant === "info"
                  ? "alert-info"
                  : variant === "error"
                    ? "alert-error"
                    : variant === "success"
                      ? "alert-success"
                      : variant === "warn"
                        ? "alert-warning"
                        : "",
              )}
            >
              <span>{message}</span>
            </div>
          ))}
        </div>
      ) : null}
    </ToastContext>
  );
};

export function useToast() {
  return useContext(ToastContext);
}
