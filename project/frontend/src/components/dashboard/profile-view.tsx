"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import api, { githubApi } from "@/lib/api";

interface ExperienceEntry {
  company: string;
  title: string;
  dates: string;
  location?: string;
  highlights: string[];
}

interface EducationEntry {
  school: string;
  degree: string;
  field: string;
  dates: string;
  location?: string;
  gpa?: string;
}

interface CertificationEntry {
  name: string;
  issuer: string;
  date: string;
  credential_id?: string;
  url?: string;
}



interface ProfileData {
  id: string;
  email: string;
  name?: string;
  headline?: string;
  summary?: string;
  location?: string;
  phone?: string;
  website?: string;
  linkedin_url?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  country?: string;
  institution?: string;
  degree?: string;
  field_of_study?: string;
  graduation_year?: string;
  experience?: ExperienceEntry[];
  education?: EducationEntry[];
  skills?: string[];
  certifications?: CertificationEntry[];
  achievements?: string[];
}

export function ProfileView({ externalRefreshKey = 0 }: { externalRefreshKey?: number }) {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const { toast } = useToast();

  // GitHub ingestion state
  const [ingesting, setIngesting] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<string>("none");
  const [ingestionSummary, setIngestionSummary] = useState<{
    total: number; processed: number; failed: number; lastRunAt: string;
  } | null>(null);
  const [projects, setProjects] = useState<Array<Record<string, unknown>>>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadProfile();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey, externalRefreshKey]);

  // Poll ingestion status and load projects on mount
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const loadProjects = useCallback(async () => {
    try {
      const res = await githubApi.listProjects();
      setProjects(res.data as Array<Record<string, unknown>>);
    } catch { /* ignore */ }
  }, []);

  const pollCountRef = useRef(0);
  const MAX_POLLS = 40; // 40 × 3s = 2 minutes max

  const pollIngestionStatus = useCallback(async () => {
    try {
      const res = await githubApi.getIngestStatus();
      const s = res.data.status;
      setIngestionStatus(s);
      setIngestionSummary(res.data.summary);

      if (s === "done") {
        stopPolling();
        setIngesting(false);
        await loadProjects();
        toast({ title: "Import Complete", description: `${res.data.summary?.processed ?? 0} projects imported.` });
      } else if (s === "failed" || s === "stale") {
        stopPolling();
        setIngesting(false);
        if (s === "stale") {
          toast({ title: "Import Timed Out", description: "The previous import did not complete. Please try again.", variant: "destructive" });
        } else {
          toast({ title: "Import Failed", description: "Check your GitHub connection and try again.", variant: "destructive" });
        }
      } else {
        // Safety cap: stop polling after MAX_POLLS attempts
        pollCountRef.current += 1;
        if (pollCountRef.current >= MAX_POLLS) {
          stopPolling();
          setIngesting(false);
          toast({ title: "Import Timed Out", description: "The import is taking too long. Please try again.", variant: "destructive" });
        }
      }
    } catch {
      stopPolling();
      setIngesting(false);
    }
  }, [stopPolling, loadProjects, toast]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollCountRef.current = 0;
    setIngesting(true);
    pollRef.current = setInterval(pollIngestionStatus, 3000);
    // Also poll immediately
    pollIngestionStatus();
  }, [stopPolling, pollIngestionStatus]);

  useEffect(() => {
    // On mount: only resume polling if a sync is actively running.
    // Never auto-trigger a new sync — user must click the button.
    (async () => {
      try {
        const res = await githubApi.getIngestStatus();
        const s = res.data.status;
        setIngestionStatus(s);
        setIngestionSummary(res.data.summary);
        if (s === "in_progress") {
          startPolling();
        }
      } catch { /* ignore */ }
      await loadProjects();
    })();
    return () => stopPolling();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRefreshRepos = async () => {
    setIngesting(true);
    try {
      await githubApi.ingest(false);
      startPolling();
    } catch {
      // background job started — poll for completion
      startPolling();
    }
  };

  const loadProfile = async () => {
    try {
      setLoading(true);
      const response = await api.get("/api/auth/profile");
      setProfile(response.data);
    } catch (error: unknown) {
      const msg =
        (error as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail || "Failed to load profile";
      toast({
        title: "Error",
        description: msg,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!profile) return;

    try {
      setSaving(true);
      const response = await api.put("/api/auth/profile", {
        name: profile.name,
        headline: profile.headline,
        summary: profile.summary,
        location: profile.location,
        phone: profile.phone,
        website: profile.website,
        linkedin_url: profile.linkedin_url,
        address_line1: profile.address_line1,
        address_line2: profile.address_line2,
        city: profile.city,
        state: profile.state,
        zip_code: profile.zip_code,
        country: profile.country,
        institution: profile.institution,
        degree: profile.degree,
        field_of_study: profile.field_of_study,
        graduation_year: profile.graduation_year,
        experience: profile.experience,
        education: profile.education,
        skills: profile.skills,
        certifications: profile.certifications,
        achievements: profile.achievements,
      });
      setProfile(response.data);
      toast({
        title: "Success",
        description: "Profile updated successfully",
      });
    } catch (error: unknown) {
      const msg =
        (error as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail || "Failed to save profile";
      toast({
        title: "Error",
        description: msg,
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field: keyof ProfileData, value: any) => {
    if (profile) {
      setProfile({ ...profile, [field]: value });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading profile...</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">No profile data found</p>
          <p className="text-sm text-muted-foreground">Upload a resume in Settings to auto-fill your profile</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save Changes"}
        </Button>
      </div>

      {/* Basic Information */}
      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
          <CardDescription>Your personal details and contact information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Full Name</Label>
              <Input
                id="name"
                value={profile.name || ""}
                onChange={(e) => handleChange("name", e.target.value)}
                placeholder="Your full name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                value={profile.email || ""}
                disabled
                className="bg-muted"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="headline">Headline</Label>
            <Input
              id="headline"
              value={profile.headline || ""}
              onChange={(e) => handleChange("headline", e.target.value)}
              placeholder="Your professional headline"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="summary">Summary</Label>
            <Textarea
              id="summary"
              value={profile.summary || ""}
              onChange={(e) => handleChange("summary", e.target.value)}
              placeholder="Professional summary"
              rows={5}
            />
          </div>
        </CardContent>
      </Card>

      {/* Contact Information */}
      <Card>
        <CardHeader>
          <CardTitle>Contact Information</CardTitle>
          <CardDescription>How people can reach you</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                value={profile.phone || ""}
                onChange={(e) => handleChange("phone", e.target.value)}
                placeholder="+1-234-567-8900"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="location">Location</Label>
              <Input
                id="location"
                value={profile.location || ""}
                onChange={(e) => handleChange("location", e.target.value)}
                placeholder="City, State"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="website">Website</Label>
              <Input
                id="website"
                value={profile.website || ""}
                onChange={(e) => handleChange("website", e.target.value)}
                placeholder="https://yourwebsite.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="linkedin_url">LinkedIn</Label>
              <Input
                id="linkedin_url"
                value={profile.linkedin_url || ""}
                onChange={(e) => handleChange("linkedin_url", e.target.value)}
                placeholder="https://linkedin.com/in/yourprofile"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Address */}
      <Card>
        <CardHeader>
          <CardTitle>Address</CardTitle>
          <CardDescription>Your mailing address</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="address_line1">Address Line 1</Label>
            <Input
              id="address_line1"
              value={profile.address_line1 || ""}
              onChange={(e) => handleChange("address_line1", e.target.value)}
              placeholder="Street address"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="address_line2">Address Line 2</Label>
            <Input
              id="address_line2"
              value={profile.address_line2 || ""}
              onChange={(e) => handleChange("address_line2", e.target.value)}
              placeholder="Apartment, suite, etc. (optional)"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="city">City</Label>
              <Input
                id="city"
                value={profile.city || ""}
                onChange={(e) => handleChange("city", e.target.value)}
                placeholder="City"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="state">State</Label>
              <Input
                id="state"
                value={profile.state || ""}
                onChange={(e) => handleChange("state", e.target.value)}
                placeholder="State"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="zip_code">ZIP Code</Label>
              <Input
                id="zip_code"
                value={profile.zip_code || ""}
                onChange={(e) => handleChange("zip_code", e.target.value)}
                placeholder="ZIP"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="country">Country</Label>
            <Input
              id="country"
              value={profile.country || ""}
              onChange={(e) => handleChange("country", e.target.value)}
              placeholder="Country"
            />
          </div>
        </CardContent>
      </Card>

      {/* Work Experience */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Work Experience</CardTitle>
              <CardDescription>Your professional work history</CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                const newExp: ExperienceEntry = {
                  company: "",
                  title: "",
                  dates: "",
                  location: "",
                  highlights: [""],
                };
                handleChange("experience", [...(profile.experience || []), newExp]);
              }}
            >
              Add Experience
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {(!profile.experience || profile.experience.length === 0) ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No work experience added yet. Click "Add Experience" to get started.
            </p>
          ) : (
            profile.experience.map((exp, idx) => (
              <div key={idx} className="border rounded-lg p-4 space-y-4">
                <div className="flex justify-between items-start">
                  <h4 className="font-semibold">Experience {idx + 1}</h4>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const newExperience = profile.experience!.filter((_, i) => i !== idx);
                      handleChange("experience", newExperience);
                    }}
                  >
                    Remove
                  </Button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Company</Label>
                    <Input
                      value={exp.company}
                      onChange={(e) => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].company = e.target.value;
                        handleChange("experience", newExperience);
                      }}
                      placeholder="Company name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Job Title</Label>
                    <Input
                      value={exp.title}
                      onChange={(e) => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].title = e.target.value;
                        handleChange("experience", newExperience);
                      }}
                      placeholder="e.g., Senior Software Engineer"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Dates</Label>
                    <Input
                      value={exp.dates}
                      onChange={(e) => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].dates = e.target.value;
                        handleChange("experience", newExperience);
                      }}
                      placeholder="e.g., Jan 2020 - Present"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Location (optional)</Label>
                    <Input
                      value={exp.location || ""}
                      onChange={(e) => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].location = e.target.value;
                        handleChange("experience", newExperience);
                      }}
                      placeholder="e.g., San Francisco, CA"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label>Key Achievements / Responsibilities</Label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].highlights.push("");
                        handleChange("experience", newExperience);
                      }}
                    >
                      Add Highlight
                    </Button>
                  </div>
                  {exp.highlights.map((highlight, hIdx) => (
                    <div key={hIdx} className="flex gap-2">
                      <Input
                        value={highlight}
                        onChange={(e) => {
                          const newExperience = [...profile.experience!];
                          newExperience[idx].highlights[hIdx] = e.target.value;
                          handleChange("experience", newExperience);
                        }}
                        placeholder="Describe your achievement or responsibility"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const newExperience = [...profile.experience!];
                          newExperience[idx].highlights = newExperience[idx].highlights.filter((_, i) => i !== hIdx);
                          handleChange("experience", newExperience);
                        }}
                      >
                        ×
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Education (Multiple Entries) */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Education</CardTitle>
              <CardDescription>Your educational background</CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                const newEdu: EducationEntry = {
                  school: "",
                  degree: "",
                  field: "",
                  dates: "",
                  location: "",
                  gpa: "",
                };
                handleChange("education", [...(profile.education || []), newEdu]);
              }}
            >
              Add Education
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {(!profile.education || profile.education.length === 0) ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground text-center py-4">
                No education entries added yet. Click "Add Education" to get started.
              </p>

              {/* Legacy single education fields */}
              {(profile.institution || profile.degree || profile.field_of_study) && (
                <div className="border rounded-lg p-4 space-y-4 bg-muted/50">
                  <p className="text-sm font-medium">Legacy Education Entry</p>
                  <div className="space-y-2">
                    <Label htmlFor="institution">Institution</Label>
                    <Input
                      id="institution"
                      value={profile.institution || ""}
                      onChange={(e) => handleChange("institution", e.target.value)}
                      placeholder="University or college name"
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="degree">Degree</Label>
                      <Input
                        id="degree"
                        value={profile.degree || ""}
                        onChange={(e) => handleChange("degree", e.target.value)}
                        placeholder="Bachelor of Science"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="field_of_study">Field of Study</Label>
                      <Input
                        id="field_of_study"
                        value={profile.field_of_study || ""}
                        onChange={(e) => handleChange("field_of_study", e.target.value)}
                        placeholder="Computer Science"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="graduation_year">Graduation Year</Label>
                    <Input
                      id="graduation_year"
                      value={profile.graduation_year || ""}
                      onChange={(e) => handleChange("graduation_year", e.target.value)}
                      placeholder="2024"
                    />
                  </div>
                </div>
              )}
            </div>
          ) : (
            profile.education.map((edu, idx) => (
              <div key={idx} className="border rounded-lg p-4 space-y-4">
                <div className="flex justify-between items-start">
                  <h4 className="font-semibold">Education {idx + 1}</h4>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const newEducation = profile.education!.filter((_, i) => i !== idx);
                      handleChange("education", newEducation);
                    }}
                  >
                    Remove
                  </Button>
                </div>

                <div className="space-y-2">
                  <Label>Institution/School</Label>
                  <Input
                    value={edu.school}
                    onChange={(e) => {
                      const newEducation = [...profile.education!];
                      newEducation[idx].school = e.target.value;
                      handleChange("education", newEducation);
                    }}
                    placeholder="University or college name"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Degree</Label>
                    <Input
                      value={edu.degree}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].degree = e.target.value;
                        handleChange("education", newEducation);
                      }}
                      placeholder="e.g., Bachelor of Science"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Field of Study</Label>
                    <Input
                      value={edu.field}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].field = e.target.value;
                        handleChange("education", newEducation);
                      }}
                      placeholder="e.g., Computer Science"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Dates</Label>
                    <Input
                      value={edu.dates}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].dates = e.target.value;
                        handleChange("education", newEducation);
                      }}
                      placeholder="e.g., 2018 - 2022"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Location (optional)</Label>
                    <Input
                      value={edu.location || ""}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].location = e.target.value;
                        handleChange("education", newEducation);
                      }}
                      placeholder="e.g., Boston, MA"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>GPA (optional)</Label>
                    <Input
                      value={edu.gpa || ""}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].gpa = e.target.value;
                        handleChange("education", newEducation);
                      }}
                      placeholder="e.g., 3.8/4.0"
                    />
                  </div>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Certifications */}
      <Card className="border-l-4 border-l-amber-400">
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="flex items-center gap-2">
                <span className="text-2xl">🏆</span>
                Certifications
              </CardTitle>
              <CardDescription>Your professional certifications and credentials</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={async () => {
                  if (!profile.linkedin_url) {
                    toast({
                      title: "LinkedIn URL Required",
                      description: "Please add your LinkedIn URL to your profile first!",
                      variant: "destructive",
                    });
                    return;
                  }

                  try {
                    toast({
                      title: "Opening LinkedIn…",
                      description: "A browser will open. Please log in to LinkedIn if needed, then wait while we scrape your certifications.",
                    });

                    const response = await api.post('/api/auth/linkedin/scrape-certifications');

                    if (response.data.success) {
                      // Reload profile to get updated certifications
                      const updatedProfile = await api.get('/api/auth/profile');
                      setProfile(updatedProfile.data);

                      toast({
                        title: "Success!",
                        description: response.data.message,
                      });
                    }
                  } catch (error: any) {
                    console.error('Error scraping LinkedIn:', error);
                    toast({
                      title: "Scraping Failed",
                      description: error.response?.data?.detail || "Failed to scrape LinkedIn. Make sure you logged in when the browser opened.",
                      variant: "destructive",
                    });
                  }
                }}
                className="border-primary/30 hover:bg-primary/5"
              >
                <svg className="h-4 w-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                </svg>
                Import from LinkedIn
              </Button>
              <Button
                onClick={() => {
                  const newCert: CertificationEntry = {
                    name: "",
                    issuer: "",
                    date: "",
                    credential_id: "",
                    url: "",
                  };
                  handleChange("certifications", [...(profile.certifications || []), newCert]);
                }}
                className="bg-amber-600 hover:bg-amber-700"
              >
                Add Manually
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {(!profile.certifications || profile.certifications.length === 0) ? (
            <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg">
              <p className="text-sm">
                No certifications added yet. Import from LinkedIn or add manually.
              </p>
            </div>
          ) : (
            profile.certifications.map((cert, idx) => (
              <div key={idx} className="p-4 border rounded-lg space-y-4 bg-amber-50 dark:bg-amber-950">
                <div className="flex justify-between items-start">
                  <h4 className="font-semibold text-foreground">Certification {idx + 1}</h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const newCertifications = profile.certifications!.filter((_, i) => i !== idx);
                      handleChange("certifications", newCertifications);
                    }}
                    className="text-destructive hover:text-destructive/80 hover:bg-destructive/5"
                  >
                    Remove
                  </Button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor={`cert-name-${idx}`}>Certification Name *</Label>
                    <Input
                      id={`cert-name-${idx}`}
                      value={cert.name}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = { ...newCertifications[idx], name: e.target.value };
                        handleChange("certifications", newCertifications);
                      }}
                      placeholder="AWS Certified Solutions Architect"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`cert-issuer-${idx}`}>Issuing Organization *</Label>
                    <Input
                      id={`cert-issuer-${idx}`}
                      value={cert.issuer}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = { ...newCertifications[idx], issuer: e.target.value };
                        handleChange("certifications", newCertifications);
                      }}
                      placeholder="Amazon Web Services"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`cert-date-${idx}`}>Issue Date *</Label>
                    <Input
                      id={`cert-date-${idx}`}
                      value={cert.date}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = { ...newCertifications[idx], date: e.target.value };
                        handleChange("certifications", newCertifications);
                      }}
                      placeholder="January 2024"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`cert-id-${idx}`}>Credential ID</Label>
                    <Input
                      id={`cert-id-${idx}`}
                      value={cert.credential_id || ""}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = { ...newCertifications[idx], credential_id: e.target.value };
                        handleChange("certifications", newCertifications);
                      }}
                      placeholder="ABC123XYZ"
                    />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor={`cert-url-${idx}`}>Credential URL</Label>
                    <Input
                      id={`cert-url-${idx}`}
                      value={cert.url || ""}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = { ...newCertifications[idx], url: e.target.value };
                        handleChange("certifications", newCertifications);
                      }}
                      placeholder="https://www.credly.com/badges/..."
                    />
                  </div>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* GitHub Projects */}
      <Card className="border-l-4 border-l-green-500">
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="flex items-center gap-2">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
                GitHub Projects
              </CardTitle>
              <CardDescription>Import and sync your GitHub repositories</CardDescription>
            </div>
            <Button
              onClick={handleRefreshRepos}
              disabled={ingesting}
              className="bg-green-600 hover:bg-green-700"
            >
              {ingesting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Importing…
                </>
              ) : (
                "Refresh Repos"
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Status region */}
          <div aria-live="polite" className="mb-4">
            {ingestionStatus === "in_progress" && (
              <p className="text-sm text-primary animate-pulse">
                Importing repositories… This may take a minute.
              </p>
            )}
            {ingestionStatus === "pending" && (
              <p className="text-sm text-[hsl(var(--accent))] animate-pulse">
                Initial import pending…
              </p>
            )}
            {ingestionStatus === "done" && ingestionSummary && (
              <p className="text-sm text-[hsl(var(--success))]">
                {ingestionSummary.processed} projects imported
                {ingestionSummary.failed > 0 && ` (${ingestionSummary.failed} failed)`}
                {ingestionSummary.lastRunAt && ` — last run ${new Date(ingestionSummary.lastRunAt).toLocaleString()}`}
              </p>
            )}
            {ingestionStatus === "failed" && (
              <p className="text-sm text-destructive">
                Import failed. Check your GitHub connection and try again.
              </p>
            )}
          </div>

          {/* Project list */}
          {projects.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg">
              <p className="text-sm">
                No projects imported yet. Click &quot;Refresh Repos&quot; to import your GitHub repositories.
              </p>
            </div>
          ) : (
            <div className="grid gap-3">
              {projects.map((proj) => (
                <div
                  key={String(proj.projectId)}
                  className="p-3 border rounded-lg flex justify-between items-start bg-card hover:bg-accent/50 transition-colors"
                >
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{String(proj.name)}</span>
                      {Number(proj.stars) > 0 && (
                        <span className="text-xs text-[hsl(var(--accent))]">
                          ★ {String(proj.stars)}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-1">
                      {String(proj.oneLiner || proj.description || "")}
                    </p>
                    {Array.isArray(proj.technologies) && proj.technologies.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(proj.technologies as string[]).slice(0, 6).map((tech) => (
                          <span
                            key={tech}
                            className="text-xs px-1.5 py-0.5 bg-muted rounded"
                          >
                            {tech}
                          </span>
                        ))}
                        {(proj.technologies as string[]).length > 6 && (
                          <span className="text-xs text-muted-foreground">
                            +{(proj.technologies as string[]).length - 6} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  {Boolean(proj.repoUrl) && (
                    <a
                      href={String(proj.repoUrl)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:text-foreground ml-2 shrink-0"
                    >
                      View ↗
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Skills */}
      <Card>
        <CardHeader>
          <CardTitle>Skills</CardTitle>
          <CardDescription>Your technical and professional skills</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="skills">Skills (comma-separated)</Label>
            <Textarea
              id="skills"
              value={profile.skills?.join(", ") || ""}
              onChange={(e) => handleChange("skills", e.target.value.split(",").map(s => s.trim()))}
              placeholder="Python, JavaScript, React, etc."
              rows={4}
            />
          </div>
        </CardContent>
      </Card>

      {/* Achievements */}
      <Card className="border-l-4 border-l-purple-500">
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="flex items-center gap-2">
                <span className="text-2xl">🌟</span>
                Achievements
              </CardTitle>
              <CardDescription>Awards, honors, and notable accomplishments — each line becomes a bullet on your resume</CardDescription>
            </div>
            <Button
              onClick={() => handleChange("achievements", [...(profile.achievements || []), ""])}
              className="bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-700 hover:to-violet-700"
            >
              Add Achievement
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {(!profile.achievements || profile.achievements.length === 0) ? (
            <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg">
              <p className="text-sm font-medium mb-1">No achievements added yet.</p>
              <p className="text-xs">
                Each bullet should be self-contained, e.g.:<br />
                <span className="italic">100% Merit Scholarship Recipient, Saveetha Engineering College (Full tuition waiver, 4 years)</span>
              </p>
            </div>
          ) : (
            profile.achievements.map((bullet, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="text-muted-foreground text-lg leading-none mt-0.5">•</span>
                <Input
                  value={bullet}
                  onChange={(e) => {
                    const updated = [...profile.achievements!];
                    updated[idx] = e.target.value;
                    handleChange("achievements", updated);
                  }}
                  placeholder="e.g. Smart India Hackathon 2025 Finalist – India's premier national innovation challenge"
                  className="flex-1"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleChange("achievements", profile.achievements!.filter((_, i) => i !== idx))}
                  className="text-destructive hover:text-destructive/80 hover:bg-destructive/5 shrink-0"
                >
                  ×
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Save Button (bottom) */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving} size="lg">
          {saving ? "Saving…" : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}
