import clsx from "clsx";
import type { ButtonHTMLAttributes } from "react";

import styles from "./button.module.css";

export const MagicButton = (props: ButtonHTMLAttributes<HTMLButtonElement>) => {
  return <button {...props} className={clsx(styles.button, props.className)} />;
};
