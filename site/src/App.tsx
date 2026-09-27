import { DemoVideo } from "./components/DemoVideo";
import { Footer } from "./components/Footer";
import { Guarantees } from "./components/Guarantees";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";
import { Install } from "./components/Install";
import { Prompts } from "./components/Prompts";
import { Proof } from "./components/Proof";

export function App() {
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <div id="top" />
      <Header />
      <main id="main">
        <Hero />
        <HowItWorks />
        <DemoVideo />
        <Guarantees />
        <Proof />
        <Install />
        <Prompts />
      </main>
      <Footer />
    </>
  );
}
