"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { ChevronsUpDownIcon, LogOutIcon, UserCircleIcon } from "lucide-react"

import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { Avatar, AvatarFallback } from "@/vendor/gui/ui/avatar"
import { Button } from "@/vendor/gui/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/vendor/gui/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/vendor/gui/ui/sidebar"

export function NavUser({
  user = {
    name: "Operator",
    email: "operator@egregore.local",
  },
}: {
  user?: {
    name: string
    email: string
  }
}) {
  const { isMobile } = useSidebar()
  const router = useRouter()
  const initials = user.name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" })
    router.push("/login")
    router.refresh()
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="min-w-0 data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="size-8 rounded-lg">
                <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
              </Avatar>
              <div className="grid min-w-0 flex-1 text-left text-sm leading-tight">
                <OverflowText className="w-full min-w-0 font-medium">{user.name}</OverflowText>
                <OverflowText className="w-full min-w-0 text-xs">{user.email}</OverflowText>
              </div>
              <ChevronsUpDownIcon className="ml-auto" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="size-8 rounded-lg">
                  <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
                </Avatar>
                <div className="grid min-w-0 flex-1 text-left text-sm leading-tight">
                  <OverflowText className="w-full min-w-0 font-medium">{user.name}</OverflowText>
                  <OverflowText className="w-full min-w-0 text-xs">{user.email}</OverflowText>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/">
                <UserCircleIcon />
                Work orders
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => void logout()}>
              <LogOutIcon />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

export function NavUserGuest() {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <Button variant="outline" size="sm" className="w-full" asChild>
          <Link href="/login">Sign in</Link>
        </Button>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
