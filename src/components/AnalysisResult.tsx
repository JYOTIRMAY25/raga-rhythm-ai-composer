
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { AudioAnalysis } from "@/types/music";

interface AnalysisResultProps {
  analysis: AudioAnalysis;
}

const AnalysisResult = ({ analysis }: AnalysisResultProps) => {
  const confidencePercent = Math.round(analysis.confidence * 100);
  
  // Determine confidence level for UI display
  const getConfidenceLevel = () => {
    if (confidencePercent >= 80) return "high";
    if (confidencePercent >= 60) return "medium";
    return "low";
  };
  
  const confidenceLevel = getConfidenceLevel();
  const confidenceColor = {
    high: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
    medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
    low: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300"
  }[confidenceLevel];

  return (
    <Card className="border-raga-secondary/20">
      <CardHeader className="bg-raga-light/50 dark:bg-raga-dark/30">
        <CardTitle className="text-raga-secondary flex items-center justify-between">
          <span>Analysis Results</span>
          <Badge className={confidenceColor}>
            {confidencePercent}% Confidence
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        {analysis.raga ? (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium">Detected Raga</h3>
              <p className="text-2xl font-bold text-raga-primary">{analysis.raga.name}</p>
              <p className="text-sm text-muted-foreground mt-1">{analysis.raga.description}</p>
              <div className="flex items-center mt-2 space-x-2">
                <Badge variant="outline" className="bg-raga-light/50 text-raga-dark">
                  {analysis.raga.time}
                </Badge>
                <Badge variant="outline" className="bg-raga-light/50 text-raga-dark">
                  {analysis.raga.mood}
                </Badge>
              </div>
            </div>
            
            <Separator />
            
            {analysis.tala && (
              <div>
                <h3 className="text-lg font-medium">Detected Tala</h3>
                <p className="text-xl font-semibold">{analysis.tala.name} ({analysis.tala.beats} beats)</p>
                <p className="text-sm text-muted-foreground mt-1">{analysis.tala.pattern}</p>
              </div>
            )}
            
            {analysis.tempo && (
              <div>
                <h3 className="text-lg font-medium">Estimated Tempo</h3>
                <p className="text-xl font-semibold">{analysis.tempo} BPM</p>
              </div>
            )}
            
            <Separator />
            
            <div>
              <h3 className="text-lg font-medium">Detected Notes</h3>
              <div className="flex flex-wrap gap-2 mt-2">
                {analysis.notes.map((note, index) => (
                  <Badge key={index} variant="secondary">
                    {note}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="py-8 text-center">
            <p className="text-muted-foreground">
              Could not detect raga with sufficient confidence.
              <br />Try uploading a clearer recording with more distinctive phrases.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AnalysisResult;
