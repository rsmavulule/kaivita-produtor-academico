export type ProductFormState = {
  name: string;
  description: string;
  category: string;
  imageRef: string;
  imageUseConfirmed: boolean;
  formError?: string;
  nameError?: string;
  descriptionError?: string;
  categoryError?: string;
  imageError?: string;
  lostAccess?: boolean;
  accessChanged?: boolean;
};

export type ArchiveFormState = {
  formError?: string;
  lostAccess?: boolean;
  accessChanged?: boolean;
};

export const emptyProductState: ProductFormState = {
  name: "",
  description: "",
  category: "",
  imageRef: "",
  imageUseConfirmed: false,
};
