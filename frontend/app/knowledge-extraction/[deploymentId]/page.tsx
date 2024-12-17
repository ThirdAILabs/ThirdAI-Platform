'use client';

import { useState, useRef, useEffect, ChangeEvent } from 'react';
import { useParams } from 'next/navigation';
import { Container, Dialog, DialogTitle, DialogContent } from '@mui/material';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useKnowledgeExtractionEndpoints, Question, Report, QuestionResult } from '@/lib/backend';

interface ResultsViewProps {
  report: Report;
  onClose: () => void;
}

const ResultsView = ({ report }: ResultsViewProps) => {
  if (!report.content) return null;

  return (
    <div className="space-y-6 mt-4">
      {report.content.results.map((result: QuestionResult) => (
        <div key={result.question_id} className="border rounded-lg p-4">
          <h3 className="font-medium mb-2">{result.question}</h3>
          <p className="text-gray-700 mb-4">{result.answer}</p>
          <div className="space-y-2">
            <h4 className="font-medium text-sm text-gray-500">References:</h4>
            {result.references.map((ref, idx) => (
              <div key={idx} className="text-sm bg-gray-50 p-2 rounded">
                <p className="text-gray-600">{ref.text}</p>
                <p className="text-gray-400 text-xs mt-1">Source: {ref.source}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

const QuestionItem = ({
  question,
  onEdit,
  onDelete,
}: {
  question: Question;
  onEdit: (id: string, text: string) => void;
  onDelete: (id: string) => void;
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(question.question_text);

  const handleConfirm = () => {
    onEdit(question.question_id, editText);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditText(question.question_text);
    setIsEditing(false);
  };

  return (
    <div key={question.question_id} className="flex items-center gap-2">
      {isEditing ? (
        <>
          <Input
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="flex-grow"
          />
          <Button onClick={handleConfirm} variant="default">
            Save
          </Button>
          <Button onClick={handleCancel} variant="outline">
            Cancel
          </Button>
        </>
      ) : (
        <>
          <div className="flex-grow p-2 border rounded">{question.question_text}</div>
          <Button onClick={() => setIsEditing(true)} variant="outline">
            Edit
          </Button>
        </>
      )}
      <Button onClick={() => onDelete(question.question_id)} variant="destructive">
        Delete
      </Button>
    </div>
  );
};

export default function Page(): JSX.Element {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showQuestions, setShowQuestions] = useState<boolean>(false);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [newQuestionText, setNewQuestionText] = useState('');

  const params = useParams();
  const workflowId = params?.deploymentId as string;
  const {
    listReports,
    createReport,
    getReport,
    deleteReport,
    addQuestion,
    getQuestions,
    deleteQuestion,
    editQuestion,
  } = useKnowledgeExtractionEndpoints(workflowId);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [fetchedQuestions, fetchedReportStatuses] = await Promise.all([
          getQuestions(),
          listReports(),
        ]);

        setQuestions(fetchedQuestions);
        const reportDetails = await Promise.all(
          fetchedReportStatuses.map((r) => getReport(r.report_id))
        );
        setReports(reportDetails);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const getFileName = (path: string): string => path.split('/').pop() || path;

  const filteredReports = reports.filter(
    (report: Report): boolean =>
      report.documents?.some((doc) =>
        getFileName(doc.path).toLowerCase().includes(searchQuery.toLowerCase())
      ) ?? false
  );

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      try {
        const reportId = await createReport(files);
        const report = await getReport(reportId);
        setReports([...reports, report]);
      } catch (error) {
        console.error('Error uploading file:', error);
      }
    }
  };

  const handleDeleteReport = async (reportId: string) => {
    try {
      await deleteReport(reportId);
      setReports(reports.filter((r) => r.report_id !== reportId));
    } catch (error) {
      console.error('Error deleting report:', error);
    }
  };

  const handleAddQuestion = async () => {
    try {
      if (!newQuestionText.trim()) return;
      await addQuestion(newQuestionText.trim());
      const updatedQuestions = await getQuestions();
      setQuestions(updatedQuestions);
      setNewQuestionText('');
    } catch (error) {
      console.error('Error adding question:', error);
    }
  };

  const handleEditQuestion = async (questionId: string, newText: string) => {
    try {
      await editQuestion(questionId, newText);
      const updatedQuestions = await getQuestions();
      setQuestions(updatedQuestions);
    } catch (error) {
      console.error('Error editing question:', error);
    }
  };

  const handleDeleteQuestion = async (questionId: string) => {
    try {
      await deleteQuestion(questionId);
      setQuestions(questions.filter((q) => q.question_id !== questionId));
    } catch (error) {
      console.error('Error deleting question:', error);
    }
  };

  return (
    <div className="bg-muted min-h-screen">
      <div className="fixed top-6 right-6">
        <Button onClick={() => setShowQuestions(!showQuestions)} className="bg-blue-500 text-white">
          Edit Questions
        </Button>
      </div>

      {!showQuestions ? (
        <Container className="pt-20 max-w-4xl">
          <Card className="bg-white p-6">
            <CardHeader>
              <h2 className="text-2xl font-bold mb-4">Select Document</h2>
              <Input
                type="search"
                placeholder="Search files..."
                value={searchQuery}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                className="mb-4"
              />
            </CardHeader>
            <div className="space-y-2">
              <Button
                onClick={() => fileInputRef.current?.click()}
                className="w-full text-left p-4 hover:bg-gray-50"
              >
                + Add new file
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileUpload}
                multiple
              />
              {filteredReports.map((report: Report) => (
                <div key={report.report_id} className="space-y-2">
                  {report.documents.map((doc) => (
                    <div
                      key={doc.path}
                      className="flex items-center justify-between p-4 hover:bg-gray-50 border rounded-md"
                    >
                      <div className="flex flex-col">
                        <span className="font-medium">{getFileName(doc.path)}</span>
                        <span className="text-sm text-gray-500">
                          Submitted: {new Date(report.submitted_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-4">
                        <Badge
                          variant={report.status === 'complete' ? 'default' : 'secondary'}
                          className={`capitalize ${
                            report.status === 'complete'
                              ? 'bg-green-100 text-green-800 hover:bg-green-100'
                              : report.status === 'failed'
                                ? 'bg-red-100 text-red-800 hover:bg-red-100'
                                : 'bg-yellow-100 text-yellow-800 hover:bg-yellow-100'
                          }`}
                        >
                          {report.status}
                        </Badge>
                        {report.status === 'complete' && report.content && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setSelectedReport(report)}
                          >
                            View Results
                          </Button>
                        )}
                        <Button
                          onClick={() => handleDeleteReport(report.report_id)}
                          variant="destructive"
                          size="sm"
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </Card>
        </Container>
      ) : (
        <Container className="pt-20 max-w-4xl">
          <Card className="bg-white p-6">
            <CardHeader>
              <h2 className="text-2xl font-bold mb-4">Edit Questions</h2>
            </CardHeader>
            <div className="space-y-4">
              <div className="flex gap-2">
                <Input
                  value={newQuestionText}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setNewQuestionText(e.target.value)
                  }
                  placeholder="Enter new question..."
                  className="flex-grow"
                />
                <Button onClick={handleAddQuestion} disabled={!newQuestionText.trim()}>
                  Add Question
                </Button>
              </div>
              {questions.map((question: Question) => (
                <QuestionItem
                  key={question.question_id}
                  question={question}
                  onEdit={handleEditQuestion}
                  onDelete={handleDeleteQuestion}
                />
              ))}
            </div>
          </Card>
        </Container>
      )}

      <Dialog
        open={!!selectedReport}
        onClose={() => setSelectedReport(null)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>Report Results</DialogTitle>
        <DialogContent>
          {selectedReport && (
            <ResultsView report={selectedReport} onClose={() => setSelectedReport(null)} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
