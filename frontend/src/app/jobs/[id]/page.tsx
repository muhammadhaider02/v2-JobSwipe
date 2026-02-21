"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  ArrowLeft, 
  ExternalLink, 
  Loader2, 
  MapPin, 
  Building2, 
  Clock,
  Globe,
  TrendingUp,
  Code
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

type Job = {
  id: string;
  url: string;
  source: string;
  raw_html_path: string;
  scraped_at: string;
  city: string | null;
  country: string | null;
  experience_level: string | null;
  job_type: string | null;
  user_id: string;
  status: string;
};

export default function JobDetailsPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadJob();
  }, [params.id]);

  const loadJob = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/jobs/${params.id}`
      );

      if (!response.ok) {
        throw new Error("Job not found");
      }

      const data = await response.json();
      setJob(data.job);
    } catch (err: any) {
      setError(err.message || "Failed to load job");
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getSourceBadgeColor = (source: string) => {
    switch (source) {
      case "rozee":
        return "bg-blue-100 text-blue-800 border-blue-300";
      case "greenhouse":
        return "bg-green-100 text-green-800 border-green-300";
      case "lever":
        return "bg-purple-100 text-purple-800 border-purple-300";
      default:
        return "bg-gray-100 text-gray-800 border-gray-300";
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading job details...</p>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-6">
        <Card className="p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <ExternalLink className="w-8 h-8 text-red-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Job Not Found</h2>
          <p className="text-gray-600 mb-6">{error || "This job listing could not be found."}</p>
          <Button
            onClick={() => router.push("/jobs")}
            className="bg-blue-600 hover:bg-blue-700"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Jobs
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Back Button */}
        <Button
          onClick={() => router.push("/jobs")}
          variant="ghost"
          className="mb-6 hover:bg-white/50"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Jobs
        </Button>

        {/* Job Card */}
        <Card className="p-8 shadow-xl">
          {/* Header */}
          <div className="mb-6">
            <div className="flex flex-wrap gap-2 mb-4">
              <span
                className={`px-3 py-1 rounded-full text-sm font-medium border ${getSourceBadgeColor(
                  job.source
                )}`}
              >
                {job.source.toUpperCase()}
              </span>
              {job.job_type && (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800 border border-gray-300">
                  {job.job_type.charAt(0).toUpperCase() + job.job_type.slice(1)}
                </span>
              )}
              {job.experience_level && (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800 border border-yellow-300">
                  {job.experience_level.charAt(0).toUpperCase() + job.experience_level.slice(1)} Level
                </span>
              )}
              <span className="px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 border border-green-300">
                {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
              </span>
            </div>

            <h1 className="text-3xl font-bold text-gray-900 mb-4">
              Job Listing from {job.source}
            </h1>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-600">
              {job.city && (
                <div className="flex items-center gap-2">
                  <MapPin className="w-5 h-5 text-blue-600" />
                  <span>
                    {job.city}
                    {job.country && `, ${job.country}`}
                  </span>
                </div>
              )}
              
              {job.experience_level && (
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-blue-600" />
                  <span>{job.experience_level.charAt(0).toUpperCase() + job.experience_level.slice(1)} Level</span>
                </div>
              )}

              {job.job_type && (
                <div className="flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-blue-600" />
                  <span>{job.job_type.charAt(0).toUpperCase() + job.job_type.slice(1)}</span>
                </div>
              )}

              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-blue-600" />
                <span>Scraped {formatDate(job.scraped_at)}</span>
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-gray-200 my-6"></div>

          {/* Details */}
          <div className="space-y-6">
            {/* URL Section */}
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
                <Globe className="w-5 h-5 text-blue-600" />
                Job Listing URL
              </h2>
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 hover:underline break-all inline-flex items-center gap-2"
              >
                {job.url}
                <ExternalLink className="w-4 h-4 flex-shrink-0" />
              </a>
            </div>

            {/* Source Info */}
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
                <Building2 className="w-5 h-5 text-blue-600" />
                Source Information
              </h2>
              <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">Platform:</span>
                  <span className="font-medium text-gray-900">{job.source.toUpperCase()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Job ID:</span>
                  <span className="font-mono text-sm text-gray-900">{job.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Status:</span>
                  <span className="font-medium text-green-600">{job.status}</span>
                </div>
              </div>
            </div>

            {/* Raw Data Info */}
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
                <Code className="w-5 h-5 text-blue-600" />
                Raw Data
              </h2>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm text-gray-600 mb-2">
                  Raw HTML data has been saved for this job listing. This data will be parsed in a future update to extract:
                </p>
                <ul className="text-sm text-gray-600 space-y-1 ml-4 list-disc">
                  <li>Job title and company name</li>
                  <li>Detailed job description</li>
                  <li>Required skills and qualifications</li>
                  <li>Salary range (if available)</li>
                  <li>Application deadline</li>
                </ul>
                <p className="text-xs text-gray-500 mt-3">
                  Stored at: <code className="bg-gray-200 px-1 rounded">{job.raw_html_path}</code>
                </p>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="mt-8 flex gap-4">
            <Button
              onClick={() => window.open(job.url, "_blank")}
              className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              <ExternalLink className="w-5 h-5 mr-2" />
              View on {job.source.charAt(0).toUpperCase() + job.source.slice(1)}
            </Button>
            <Button
              onClick={() => router.push("/jobs")}
              variant="outline"
              className="border-2"
            >
              <ArrowLeft className="w-5 h-5 mr-2" />
              Back to Search
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
