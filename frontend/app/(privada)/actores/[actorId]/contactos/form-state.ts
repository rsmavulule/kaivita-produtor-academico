import type { ContactChannel } from "../../../../../lib/contact-view";

export type ContactFormState = {
  channel: ContactChannel;
  value: string;
  formError?: string;
  channelError?: string;
  valueError?: string;
  lostAccess?: boolean;
};

export type GrantFormState = {
  revision: number;
  channel: ContactChannel;
  value: string;
  formError?: string;
  lostAccess?: boolean;
};

export type ConfirmFormState = {
  formError?: string;
  lostAccess?: boolean;
};

export function emptyContactState(): ContactFormState {
  return { channel: "email", value: "" };
}
