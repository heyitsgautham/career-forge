"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";

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
  skills?: string[];
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const response = await api.get("/auth/profile");
      setProfile(response.data);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to load profile",
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
      const response = await api.put("/auth/profile", {
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
        skills: profile.skills,
      });
      setProfile(response.data);
      toast({
        title: "Success",
        description: "Profile updated successfully",
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to save profile",
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
      <div className="flex items-center justify-center h-screen">
        <p>Loading profile...</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p>Profile not found</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Profile</h1>
          <p className="text-muted-foreground">View and edit your profile information</p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>

      <div className="space-y-6">
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

        {/* Education */}
        <Card>
          <CardHeader>
            <CardTitle>Education</CardTitle>
            <CardDescription>Your educational background</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
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

        {/* Save Button (bottom) */}
        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={saving} size="lg">
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>
    </div>
  );
}
