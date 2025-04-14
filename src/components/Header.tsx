
import { useNavigate, useLocation } from "react-router-dom";
import { Music } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "./ThemeToggle";

const Header = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const isHome = location.pathname === "/";
  const isApp = location.pathname === "/app";

  return (
    <header className="border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 max-w-screen-2xl items-center">
        <div className="flex items-center space-x-2 mr-4" onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
          <Music className="h-6 w-6 text-raga-primary" />
          <span className="font-bold text-xl bg-gradient-to-r from-raga-primary to-raga-secondary bg-clip-text text-transparent">
            Raga Rhythm
          </span>
        </div>
        
        <nav className="flex items-center space-x-4 lg:space-x-6 mx-6">
          <Button 
            variant={isHome ? "default" : "ghost"}
            className={isHome ? "bg-raga-primary/10 text-raga-primary hover:bg-raga-primary/20 hover:text-raga-primary" : ""}
            onClick={() => navigate("/")}
          >
            Home
          </Button>
          <Button 
            variant={isApp ? "default" : "ghost"}
            className={isApp ? "bg-raga-secondary/10 text-raga-secondary hover:bg-raga-secondary/20 hover:text-raga-secondary" : ""}
            onClick={() => navigate("/app")}
          >
            App
          </Button>
        </nav>
        
        <div className="ml-auto flex items-center space-x-4">
          <ThemeToggle />
          {!isApp && (
            <Button 
              onClick={() => navigate("/app")} 
              className="bg-raga-primary hover:bg-raga-primary/90"
            >
              Launch App
            </Button>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
