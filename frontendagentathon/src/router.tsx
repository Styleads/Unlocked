import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { AnchorHTMLAttributes, ReactNode } from "react";

export type Route =
  | "/"
  | "/start"
  | "/details"
  | "/discovering"
  | "/questions"
  | "/results"
  | "/scheme"
  | "/plan";

const ROUTES: Route[] = ["/", "/start", "/details", "/discovering", "/questions", "/results", "/scheme", "/plan"];

function currentRoute(): Route {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  return (ROUTES as string[]).includes(path) ? (path as Route) : "/";
}

const RouterContext = createContext<{ route: Route; navigate: (to: Route) => void }>({
  route: "/",
  navigate: () => {},
});

export function RouterProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState<Route>(currentRoute);

  useEffect(() => {
    const onPop = () => setRoute(currentRoute());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to: Route) => {
    if (to !== window.location.pathname) window.history.pushState(null, "", to);
    setRoute(to);
    window.scrollTo(0, 0);
  }, []);

  return <RouterContext.Provider value={{ route, navigate }}>{children}</RouterContext.Provider>;
}

export const useRouter = () => useContext(RouterContext);

type LinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { to: Route };

/** In-app link: real <a href> for accessibility, client-side navigation on plain click. */
export function Link({ to, onClick, ...rest }: LinkProps) {
  const { navigate } = useRouter();
  return (
    <a
      href={to}
      onClick={(e) => {
        onClick?.(e);
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        e.preventDefault();
        navigate(to);
      }}
      {...rest}
    />
  );
}
