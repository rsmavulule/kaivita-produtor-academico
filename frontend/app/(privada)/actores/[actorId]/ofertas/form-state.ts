export type OfferFormState = {
  productId: string;
  price: string;
  currency: string;
  quantity: string;
  unit: string;
  availability: string;
  deliveryTerms: string;
  formError?: string;
  productError?: string;
  priceError?: string;
  currencyError?: string;
  quantityError?: string;
  unitError?: string;
  availabilityError?: string;
  deliveryError?: string;
  lostAccess?: boolean;
  accessChanged?: boolean;
  contextChanged?: boolean;
};

export type TransitionFormState = {
  formError?: string;
  lostAccess?: boolean;
  accessChanged?: boolean;
  contextChanged?: boolean;
};

export const emptyOfferState: OfferFormState = {
  productId: "",
  price: "",
  currency: "",
  quantity: "",
  unit: "",
  availability: "",
  deliveryTerms: "",
};
