import { ThemeProvider } from "./ThemeContext";
import { Deck } from "./components/Deck";
import { slides } from "./slides";

export default function App() {
  return (
    <ThemeProvider>
      <Deck slides={slides} />
    </ThemeProvider>
  );
}
