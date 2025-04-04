
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowRight, FileAudio, Music, Play } from "lucide-react";

const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen mandala-bg">
      <div className="container max-w-6xl px-4 py-16 mx-auto">
        {/* Hero Section */}
        <header className="text-center mb-16">
          <h1 className="text-5xl md:text-7xl font-bold bg-gradient-to-r from-raga-primary via-raga-secondary to-raga-accent bg-clip-text text-transparent tracking-tight">
            Raga Rhythm
          </h1>
          <p className="text-3xl md:text-4xl font-medium mt-2 text-raga-secondary">AI Classical Music Composer</p>
          <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">
            Discover, analyze, and generate Indian classical music with the power of AI. 
            Experience the beauty of ragas and talas through modern technology.
          </p>
          <div className="mt-10 flex flex-col md:flex-row gap-4 justify-center">
            <Button 
              size="lg" 
              className="bg-raga-primary hover:bg-raga-primary/90 text-white px-8"
              onClick={() => navigate("/app")}
            >
              Get Started
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </div>
        </header>

        {/* Features Section */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
          <Card className="border-raga-light dark:border-raga-dark/50 overflow-hidden transform transition-all hover:scale-105 hover:shadow-lg">
            <div className="h-1 bg-gradient-to-r from-raga-primary to-raga-secondary"></div>
            <CardContent className="pt-8">
              <div className="rounded-full bg-raga-light dark:bg-raga-dark/30 p-3 w-fit mb-6">
                <FileAudio className="h-10 w-10 text-raga-primary" />
              </div>
              <h3 className="text-2xl font-semibold mb-2">Analyze Music</h3>
              <p className="text-muted-foreground">
                Upload audio recordings of classical performances and let our AI analyze the raga, 
                tala, and musical elements with cutting-edge precision.
              </p>
            </CardContent>
          </Card>

          <Card className="border-raga-light dark:border-raga-dark/50 overflow-hidden transform transition-all hover:scale-105 hover:shadow-lg">
            <div className="h-1 bg-gradient-to-r from-raga-secondary to-raga-accent"></div>
            <CardContent className="pt-8">
              <div className="rounded-full bg-raga-light dark:bg-raga-dark/30 p-3 w-fit mb-6">
                <Music className="h-10 w-10 text-raga-secondary" />
              </div>
              <h3 className="text-2xl font-semibold mb-2">Generate Compositions</h3>
              <p className="text-muted-foreground">
                Create original compositions with customizable ragas, talas, tempo, 
                and creative parameters to match your artistic vision.
              </p>
            </CardContent>
          </Card>

          <Card className="border-raga-light dark:border-raga-dark/50 overflow-hidden transform transition-all hover:scale-105 hover:shadow-lg">
            <div className="h-1 bg-gradient-to-r from-raga-accent to-raga-primary"></div>
            <CardContent className="pt-8">
              <div className="rounded-full bg-raga-light dark:bg-raga-dark/30 p-3 w-fit mb-6">
                <Play className="h-10 w-10 text-raga-accent" />
              </div>
              <h3 className="text-2xl font-semibold mb-2">Play & Download</h3>
              <p className="text-muted-foreground">
                Listen to your generated compositions directly in the browser and download 
                for use in performances, practice, or creative projects.
              </p>
            </CardContent>
          </Card>
        </section>

        {/* About Ragas Section */}
        <section className="mb-16">
          <div className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm rounded-xl p-8 border border-raga-light dark:border-raga-dark/50">
            <h2 className="text-3xl font-bold mb-6 text-center text-raga-primary">About Indian Classical Music</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <h3 className="text-xl font-semibold mb-2">Ragas</h3>
                <p className="text-muted-foreground mb-4">
                  Ragas are melodic frameworks with specific notes, patterns, and emotions. Each raga has a unique mood 
                  and is traditionally performed at specific times of day.
                </p>
                <h3 className="text-xl font-semibold mb-2">Talas</h3>
                <p className="text-muted-foreground">
                  Talas are rhythmic cycles that provide the foundation for composition and improvisation. They range 
                  from simple to complex patterns of beats organized in specific groupings.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-semibold mb-2">Performance Styles</h3>
                <p className="text-muted-foreground mb-4">
                  From the solemn Dhrupad to the expressive Khayal and romantic Thumri, Indian classical music 
                  encompasses various styles that have evolved over centuries.
                </p>
                <h3 className="text-xl font-semibold mb-2">AI Composition</h3>
                <p className="text-muted-foreground">
                  Our AI models are trained on thousands of classical performances to understand the intricate 
                  rules and nuances that make this ancient art form so profound.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="text-center mb-8">
          <div className="bg-gradient-to-r from-raga-primary/10 via-raga-secondary/10 to-raga-accent/10 rounded-xl p-10 border border-raga-light dark:border-raga-dark/50">
            <h2 className="text-3xl font-bold mb-4">Ready to explore?</h2>
            <p className="mb-8 text-muted-foreground max-w-2xl mx-auto">
              Dive into the world of Indian classical music with our AI-powered tools for analysis and composition.
            </p>
            <Button 
              size="lg" 
              className="bg-raga-secondary hover:bg-raga-secondary/90 text-white px-8"
              onClick={() => navigate("/app")}
            >
              Go to App
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </div>
        </section>

        <footer className="mt-16 text-center text-sm text-muted-foreground">
          <p>Powered by AI and Indian Classical Music theory</p>
          <p className="mt-1">© {new Date().getFullYear()} Raga Rhythm AI Composer</p>
        </footer>
      </div>
    </div>
  );
};

export default Home;
