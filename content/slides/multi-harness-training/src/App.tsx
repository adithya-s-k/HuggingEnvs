import { ThemeProvider } from "./ThemeContext";
import { Deck } from "./deck/Deck";
import { slides } from "@deck";

export default function App() {
  return (
    <ThemeProvider>
      <Deck slides={slides} />
    </ThemeProvider>
  );
}
