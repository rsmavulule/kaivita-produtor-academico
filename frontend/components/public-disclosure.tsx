import { PUBLIC_FIELD_NOTICE, PUBLIC_PUBLISH_NOTICE } from "../lib/public-offer-view";

export function PublicFieldNotice({ id }: { id: string }) {
  return (
    <p className="notice" id={id}>
      {PUBLIC_FIELD_NOTICE}
    </p>
  );
}

export function PublicPublishNotice() {
  return (
    <p className="notice" id="publish-public-notice">
      {PUBLIC_PUBLISH_NOTICE}
    </p>
  );
}
