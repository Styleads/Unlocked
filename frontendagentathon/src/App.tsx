import { RouterProvider, useRouter } from "./router";
import type { Route } from "./router";
import { SessionProvider } from "./session";
import Landing from "./pages/Landing";
import Start from "./pages/Start";
import Details from "./pages/Details";
import Discovering from "./pages/Discovering";
import Questions from "./pages/Questions";
import Results from "./pages/Results";
import Scheme from "./pages/Scheme";
import Plan from "./pages/Plan";

const PAGES: Record<Route, () => JSX.Element> = {
  "/": Landing,
  "/start": Start,
  "/details": Details,
  "/discovering": Discovering,
  "/questions": Questions,
  "/results": Results,
  "/scheme": Scheme,
  "/plan": Plan,
};

function Screen() {
  const { route } = useRouter();
  const Page = PAGES[route];
  return <Page key={route} />;
}

export default function App() {
  return (
    <SessionProvider>
      <RouterProvider>
        <Screen />
      </RouterProvider>
    </SessionProvider>
  );
}
