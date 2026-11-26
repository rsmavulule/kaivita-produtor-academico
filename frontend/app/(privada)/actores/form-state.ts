export type CreateFormState = {
  kind: string;
  displayName: string;
  location: string;
  coverageArea: string;
  roles: string[];
  formError?: string;
  kindError?: string;
  nameError?: string;
  locationError?: string;
  coverageError?: string;
  rolesError?: string;
};

export type ProfileFormState = {
  displayName: string;
  location: string;
  coverageArea: string;
  formError?: string;
  nameError?: string;
  locationError?: string;
  coverageError?: string;
  lostAccess?: boolean;
};

export type RolesFormState = {
  roles: string[];
  formError?: string;
  rolesError?: string;
  lostAccess?: boolean;
};

export const emptyCreateState: CreateFormState = {
  kind: "person",
  displayName: "",
  location: "",
  coverageArea: "",
  roles: [],
};
