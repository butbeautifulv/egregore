"use client"

import {
  OperatorMessageComposer,
  type OperatorMessageComposerProps,
} from "@/components/engagement/operator-message-composer"

export function FollowUpComposer(props: Omit<OperatorMessageComposerProps, "variant">) {
  return <OperatorMessageComposer {...props} variant="follow_up" />
}
